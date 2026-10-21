"""A complete ReAct agent with NO framework — only ``httpx`` against Ollama's /api/chat.

Two ways to call tools, both written out by hand:

* ``mode="native"`` (default): the tools are sent as JSON-Schema ``tools=[...]``; the
  model answers with structured ``tool_calls``; each result goes back as a
  ``{"role": "tool", ...}`` message; a reply without tool calls is the final answer.
  This is the provider-native function-calling loop from the course (Day 16).
* ``mode="json"``: the prompt teaches a Thought → Action → Observation JSON format and
  the reply is parsed — the fallback for models without native tool support.

Plus the loop with a step limit, and retries for transport errors and unparsable
output. It exists so the "Under the Hood" page can
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
from typing import Any, Literal

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
        mode: Literal["native", "json"] = "native",
    ) -> None:
        self.mode = mode
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

    def tool_schemas(self) -> list[dict[str, Any]]:
        """The tools in the native function-calling format (JSON Schema parameters)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            p: {"type": "string", "description": d} for p, d in t.params.items()
                        },
                        "required": list(t.params),
                    },
                },
            }
            for t in self.tools.values()
        ]

    async def _post_chat(
        self, client: httpx.AsyncClient, messages: list[dict[str, Any]], *, native: bool = False
    ) -> dict[str, Any]:
        """POST /api/chat with manual exponential backoff on transport/5xx errors."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if native:
            body["tools"] = self.tool_schemas()
        else:
            body["format"] = "json"
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
                f"call it with action_input {{{', '.join(f'{p!r}: ...' for p in expected)}}}"
            )
        try:
            out = tool.fn(**args)
            if asyncio.iscoroutine(out):
                out = await out
            return str(out)
        except Exception as exc:  # tool errors are observations, not crashes
            return f"ERROR: {type(exc).__name__}: {exc}"

    async def run(self, task: str) -> RawAgentResult:
        if self.mode == "native":
            return await self._run_native(task)
        return await self._run_json(task)

    async def _run_native(self, task: str) -> RawAgentResult:
        """Provider-native function calling: tools=[...] → tool_calls → role "tool"."""
        self.retries = 0
        started = time.perf_counter()
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": f"You are {self.name}, a careful problem solver. Use the tools "
                "whenever a calculation or lookup is needed, then give the final answer.",
            },
            {"role": "user", "content": task},
        ]
        steps: list[RawStep] = []
        calls = prompt_tokens = completion_tokens = 0
        answer: str | None = None
        reason = "max_steps"
        async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
            for iteration in range(1, self.max_steps + 1):
                data = await self._post_chat(client, messages, native=True)
                calls += 1
                prompt_tokens += int(data.get("prompt_eval_count") or 0)
                completion_tokens += int(data.get("eval_count") or 0)
                message = data.get("message") or {}
                content = str(message.get("content") or "")
                tool_calls = message.get("tool_calls") or []
                if content:
                    self.on_event("thought", {"iteration": iteration, "text": content})
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                if not tool_calls:  # no tool call: the model produced its final answer
                    step = RawStep(thought=content, final_answer=content)
                    steps.append(step)
                    answer, reason = content, "final_answer"
                    self.on_event("final", {"answer": answer})
                    break
                for call in tool_calls:
                    fn = call.get("function") or {}
                    name = str(fn.get("name") or "")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):  # some servers send a JSON string
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"input": args}
                    step = RawStep(thought=content, action=name, action_input=dict(args))
                    self.on_event("action", {"iteration": iteration, "tool": name, "args": args})
                    step.observation = await self._run_tool(name, dict(args))
                    self.on_event(
                        "observation",
                        {"iteration": iteration, "tool": name, "text": step.observation},
                    )
                    steps.append(step)
                    messages.append(
                        {"role": "tool", "content": step.observation, "tool_name": name}
                    )
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

    async def _run_json(self, task: str) -> RawAgentResult:
        """Prompted JSON ReAct for models without native tool support."""
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
