"""A complete ReAct agent with NO framework — only ``httpx`` against Ollama's /api/chat.

Everything LangChain/LangGraph would normally do is written out by hand here:
the prompt that teaches the Thought → Action → Observation format, parsing the
model's JSON, dispatching tools, the loop with a step limit, and retries for both
transport errors and unparsable output. It exists so the "Under the Hood" page can
run the same task through this agent and through the LangGraph worker side by side.

Deliberately self-contained: it does not import NEXUS's gateway, router or
reliability helpers, so what you read is all there is.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class RawTool:
    name: str
    description: str
    params: dict[str, str]  # param name -> human description
    fn: Callable[..., str] | Callable[..., Awaitable[str]]


@dataclass
class RawStep:
    thought: str
    action: str | None = None
    action_input: dict[str, Any] = field(default_factory=dict)
    observation: str | None = None
    final_answer: str | None = None


@dataclass
class RawAgentResult:
    answer: str | None
    steps: list[RawStep]
    llm_calls: int
    retries: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    stopped_reason: str


EventFn = Callable[[str, dict[str, Any]], None]

SYSTEM_TEMPLATE = """You are {name}, a careful problem solver. Solve the task step by step.

You can use these tools:
{tools}

On EVERY turn reply with exactly ONE JSON object and nothing else, either
  {{"thought": "<your reasoning>", "action": "<tool name>", "action_input": {{<arguments>}}}}
or, when you know the answer,
  {{"thought": "<your reasoning>", "final_answer": "<the answer>"}}

Rules: use a tool whenever a calculation or lookup is needed; never invent an
Observation — the system sends it to you after each action."""


def _describe(tools: list[RawTool]) -> str:
    lines = []
    for t in tools:
        args = ", ".join(f"{k}: {v}" for k, v in t.params.items())
        lines.append(f"- {t.name}({args}): {t.description}")
    return "\n".join(lines)


def _parse(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of the reply (models sometimes add prose/fences)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, depth = text.find("{"), 0
    if start < 0:
        raise ValueError("no JSON object in reply")
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                obj = json.loads(text[start : i + 1])
                if not isinstance(obj, dict):
                    raise ValueError("reply JSON is not an object")
                return obj
    raise ValueError("unterminated JSON object in reply")


class RawReActAgent:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        tools: list[RawTool],
        name: str = "RawAgent",
        max_steps: int = 6,
        temperature: float = 0.1,
        num_ctx: int = 4096,
        timeout_s: float = 120.0,
        max_http_retries: int = 3,
        max_parse_retries: int = 2,
        on_event: EventFn | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.tools = {t.name: t for t in tools}
        self.name = name
        self.max_steps = max_steps
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self.max_http_retries = max_http_retries
        self.max_parse_retries = max_parse_retries
        self.on_event = on_event or (lambda kind, data: None)
        self._transport = transport

    async def _post_chat(
        self, client: httpx.AsyncClient, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        """POST /api/chat with manual exponential backoff on transport/5xx errors."""
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        delay = 0.5
        for attempt in range(1, self.max_http_retries + 1):
            try:
                resp = await client.post(f"{self.base_url}/api/chat", json=body)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = (
                    not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code >= 500
                )
                if not retryable or attempt == self.max_http_retries:
                    raise
                self.retries += 1
                self.on_event(
                    "retry", {"layer": "transport", "attempt": attempt + 1, "reason": str(exc)}
                )
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")

    async def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool '{name}'. Available: {', '.join(self.tools)}"
        expected = list(tool.params)
        # Small models often rename the only argument ("input" for "expression").
        if len(expected) == 1 and len(args) == 1 and expected[0] not in args:
            args = {expected[0]: next(iter(args.values()))}
        unknown = set(args) - set(expected)
        if unknown:
            return (
                f"ERROR: {name} does not take {sorted(unknown)}; "
                f'call it with action_input {{{", ".join(f"{p!r}: ..." for p in expected)}}}'
            )
        try:
            out = tool.fn(**args)
            if asyncio.iscoroutine(out):
                out = await out
            return str(out)
        except Exception as exc:  # tool errors are observations, not crashes
            return f"ERROR: {type(exc).__name__}: {exc}"

    async def run(self, task: str) -> RawAgentResult:
        self.retries = 0
        started = time.perf_counter()
        messages = [
            {
                "role": "system",
                "content": SYSTEM_TEMPLATE.format(
                    name=self.name, tools=_describe(list(self.tools.values()))
                ),
            },
            {"role": "user", "content": f"Task: {task}"},
        ]
        steps: list[RawStep] = []
        calls = prompt_tokens = completion_tokens = 0
        parse_failures = 0
        answer: str | None = None
        reason = "max_steps"

        async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
            iteration = 0
            while iteration < self.max_steps:
                data = await self._post_chat(client, messages)
                calls += 1
                prompt_tokens += int(data.get("prompt_eval_count") or 0)
                completion_tokens += int(data.get("eval_count") or 0)
                reply = (data.get("message") or {}).get("content", "")

                try:
                    parsed = _parse(reply)
                except (ValueError, json.JSONDecodeError) as exc:
                    parse_failures += 1
                    self.retries += 1
                    self.on_event(
                        "retry",
                        {"layer": "validation", "attempt": parse_failures, "reason": str(exc)},
                    )
                    if parse_failures > self.max_parse_retries:
                        reason = "unparsable_output"
                        break
                    messages.append({"role": "assistant", "content": reply})
                    messages.append(
                        {
                            "role": "user",
                            "content": f"That was not valid JSON ({exc}). Reply with ONE JSON object only.",
                        }
                    )
                    continue

                iteration += 1
                step = RawStep(thought=str(parsed.get("thought", "")))
                self.on_event("thought", {"iteration": iteration, "text": step.thought})
                messages.append({"role": "assistant", "content": json.dumps(parsed)})

                if "final_answer" in parsed:
                    step.final_answer = str(parsed["final_answer"])
                    steps.append(step)
                    answer, reason = step.final_answer, "final_answer"
                    self.on_event("final", {"answer": answer})
                    break

                action = parsed.get("action")
                if not isinstance(action, str) or not action:
                    step.observation = "ERROR: reply had neither 'action' nor 'final_answer'."
                else:
                    raw_input = parsed.get("action_input") or {}
                    step.action = action
                    step.action_input = (
                        raw_input if isinstance(raw_input, dict) else {"input": raw_input}
                    )
                    self.on_event(
                        "action",
                        {"iteration": iteration, "tool": action, "args": step.action_input},
                    )
                    step.observation = await self._run_tool(action, step.action_input)
                    self.on_event(
                        "observation",
                        {"iteration": iteration, "tool": action, "text": step.observation},
                    )
                steps.append(step)
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})

        return RawAgentResult(
            answer=answer,
            steps=steps,
            llm_calls=calls,
            retries=self.retries,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            stopped_reason=reason,
        )
