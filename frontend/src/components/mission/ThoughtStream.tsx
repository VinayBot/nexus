"use client";

import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { nameOf, type AgentInfo } from "@/lib/agents";
import { cn } from "@/lib/cn";
import type { MissionView, ThoughtItem, ThoughtKind } from "@/lib/missionView";

const STYLE: Record<ThoughtKind, { label: string; color: string }> = {
  thought: { label: "Thought", color: "var(--cyan)" },
  action: { label: "Action", color: "var(--sun-gold)" },
  observation: { label: "Observation", color: "#b8a7ff" },
  final: { label: "Final", color: "var(--success)" },
  retry: { label: "Retry", color: "var(--warning)" },
  route: { label: "Route", color: "var(--text-muted)" },
  plan: { label: "Plan", color: "#ffd89a" },
  handoff: { label: "Handoff", color: "var(--sun-gold)" },
  tool: { label: "Tool", color: "var(--cyan)" },
  memory: { label: "Memory", color: "#b8a7ff" },
  risk: { label: "Risk", color: "var(--ember)" },
  guardrail: { label: "Guardrail", color: "var(--error)" },
  verdict: { label: "Verdict", color: "var(--sun-core)" },
  interrupt: { label: "Human", color: "var(--error)" },
  test: { label: "Test", color: "var(--success)" },
  system: { label: "System", color: "var(--text-faint)" },
};

const FILTERS: { id: string; kinds: ThoughtKind[] | null }[] = [
  { id: "All", kinds: null },
  { id: "ReAct", kinds: ["thought", "action", "observation", "final"] },
  { id: "Decisions", kinds: ["route", "plan", "verdict", "risk", "interrupt"] },
  { id: "Reliability", kinds: ["retry", "guardrail", "memory", "test"] },
];

function Item({ t, agents }: { t: ThoughtItem; agents?: AgentInfo[] }) {
  const s = STYLE[t.kind];
  return (
    <motion.li
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      className="rounded-lg border border-border/60 bg-black/25 px-2.5 py-2"
    >
      <div className="flex items-center gap-2 text-[11px]">
        <span
          className="rounded px-1.5 py-px font-semibold"
          style={{ color: s.color, background: `color-mix(in srgb, ${s.color} 14%, transparent)` }}
        >
          {s.label}
        </span>
        {t.agent && <span className="text-muted">{nameOf(t.agent, agents)}</span>}
        <span className="ml-auto font-mono text-[10px] text-faint">{new Date(t.ts * 1000).toLocaleTimeString()}</span>
      </div>
      <p
        className={cn(
          "mt-1 text-[12.5px] leading-snug text-text",
          t.ok === false && "text-[color-mix(in_srgb,var(--error)_80%,white)]",
        )}
      >
        {t.title}
      </p>
      {t.body && <p className="mt-0.5 line-clamp-4 font-mono text-[11px] whitespace-pre-wrap text-muted">{t.body}</p>}
    </motion.li>
  );
}

export function ThoughtStream({
  view,
  agents,
  className,
}: {
  view: MissionView;
  agents?: AgentInfo[];
  className?: string;
}) {
  const [filter, setFilter] = useState("All");
  const [follow, setFollow] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const items = useMemo(() => {
    const kinds = FILTERS.find((f) => f.id === filter)?.kinds;
    return (kinds ? view.thoughts.filter((t) => kinds.includes(t.kind)) : view.thoughts).slice(-150);
  }, [view.thoughts, filter]);

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [items, follow]);

  return (
    <section
      className={cn("panel flex min-h-0 flex-col", className)}
      aria-label="Thought stream"
      data-tour="thought-stream"
    >
      <header className="flex items-center gap-2 border-b border-border/60 px-3 py-2">
        <h2 className="panel-title text-sm text-gold">Thought Stream</h2>
        <span className="ml-auto truncate font-mono text-[10px] text-faint">
          {view.llm.calls} LLM calls · {(view.llm.prompt + view.llm.completion).toLocaleString()} tokens
        </span>
      </header>
      <div className="flex gap-1 px-3 pt-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn("chip cursor-pointer", filter === f.id && "border-border-strong text-text")}
            aria-pressed={filter === f.id}
          >
            {f.id}
          </button>
        ))}
      </div>
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget;
          setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
        }}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-2"
      >
        {items.length === 0 ? (
          <p className="py-10 text-center text-sm text-faint">
            Thoughts appear here as agents reason, act and observe.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {items.map((t) => (
              <Item key={t.id} t={t} agents={agents} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
