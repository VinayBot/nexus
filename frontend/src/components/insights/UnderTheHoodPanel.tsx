"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useState } from "react";
import { PanelIntro } from "@/components/ui/PageHeader";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Side {
  answer: string | null;
  stopped: string;
  llm_calls: number;
  retries: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  steps: {
    thought?: string;
    action?: string | null;
    input?: unknown;
    observation?: string | null;
    final?: string | null;
  }[];
}
interface Result {
  task: string;
  raw: Side;
  langgraph: Side;
}

const SIDES = [
  {
    key: "raw" as const,
    title: "Raw SDK agent",
    sub: "httpx → Ollama /api/chat · hand-written prompt, JSON parsing, loop & retries",
    file: "backend/nexus/llm/raw_react_agent.py",
  },
  {
    key: "langgraph" as const,
    title: "LangGraph ReAct worker",
    sub: "think ⇄ act subgraph · schema-constrained turns · gateway (router, governor, retries) · MCP tools",
    file: "backend/nexus/graph/subgraphs/react_worker.py",
  },
];

function Column({ side, data, winner }: { side: (typeof SIDES)[number]; data: Side; winner: boolean }) {
  return (
    <section className={cn("panel p-3", winner && "border-border-strong")}>
      <h2 className="panel-title text-base text-gold">{side.title}</h2>
      <p className="text-[11px] text-faint">{side.sub}</p>
      <p className="font-mono text-[10px] text-faint">{side.file}</p>
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        {[
          ["answer", data.answer ?? "—"],
          ["LLM calls", data.llm_calls],
          ["latency", `${(data.latency_ms / 1000).toFixed(1)}s`],
          ["prompt tok", data.prompt_tokens.toLocaleString()],
          ["output tok", data.completion_tokens.toLocaleString()],
          ["retries", data.retries],
        ].map(([k, v]) => (
          <div key={String(k)} className="rounded-lg bg-black/30 px-2 py-1.5">
            <dt className="text-[10px] text-faint">{k}</dt>
            <dd className="truncate font-mono text-sm" title={String(v)}>
              {String(v)}
            </dd>
          </div>
        ))}
      </dl>
      <ol className="mt-3 space-y-1.5">
        {data.steps.map((s, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.12 }}
            className="rounded-lg border border-border/50 p-2 text-[11.5px]"
          >
            <p>
              <span className="text-accent">Thought</span> {s.thought}
            </p>
            {s.action && (
              <p className="font-mono text-[11px]">
                <span className="text-gold">Action</span> {s.action} {JSON.stringify(s.input)}
              </p>
            )}
            {s.observation && (
              <p className="font-mono text-[11px] text-muted">
                <span className="text-[#b8a7ff]">Observation</span> {s.observation}
              </p>
            )}
            {s.final && <p className="text-success">Final: {s.final}</p>}
          </motion.li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] text-faint">stopped: {data.stopped}</p>
    </section>
  );
}

export function UnderTheHoodPanel() {
  const tasks = useQuery({ queryKey: ["lab-tasks"], queryFn: () => get<string[]>("/lab/tasks") });
  const [task, setTask] = useState("");
  const run = useMutation({ mutationFn: (t: string) => post<Result>("/lab/compare", { task: t }) });
  const r = run.data;
  const effective = task || tasks.data?.[0] || "";
  return (
    <>
      <PanelIntro
        title="Under the Hood"
        description="The same task through an agent written with no framework at all, and through the LangGraph worker the missions use. Same local model, same tools (direct functions vs the demo MCP server)."
      />
      <section className="panel flex flex-wrap items-center gap-2 p-3">
        <select
          value={task}
          onChange={(e) => setTask(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-border bg-black/40 px-2 py-2 text-sm"
          aria-label="Task"
        >
          {tasks.data?.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => run.mutate(effective)}
          disabled={run.isPending || !effective}
          className="rounded-lg bg-gradient-to-r from-[var(--sky-crimson)] to-[var(--ember)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {run.isPending ? "Both agents are working (real model)…" : "Run side by side"}
        </button>
      </section>
      {run.error && <p className="mt-2 text-xs text-danger">{run.error.message}</p>}
      {r && (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {SIDES.map((s) => (
            <Column
              key={s.key}
              side={s}
              data={r[s.key]}
              winner={r[s.key].latency_ms <= r[s.key === "raw" ? "langgraph" : "raw"].latency_ms}
            />
          ))}
        </div>
      )}
      <section className="panel mt-3 p-3 text-xs text-muted">
        <h2 className="panel-title mb-1 text-sm text-gold">What the framework buys</h2>
        <p>
          The raw agent is ~250 lines you can read top to bottom — fast and transparent, but every concern lives in one
          loop. The LangGraph worker is a typed state machine: each step is checkpointed, the loop has a declared
          max-iteration guard, retries/validation/routing come from the shared gateway, context is pruned to the
          agent&apos;s token budget, and every Thought/Action/Observation is an event the Command Center animates. Run the
          benchmark in the Benchmarks for averages over several tasks.
        </p>
      </section>
    </>
  );
}
