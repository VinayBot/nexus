"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { CountUp } from "@/components/ui/CountUp";
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
  plan: { label: "Plan", color: "var(--sun-core)" },
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

/** "Key steps" hides graph routing and system chatter: what a person wants to follow. */
const FILTERS: { id: string; kinds: ThoughtKind[] | null }[] = [
  {
    id: "Key steps",
    kinds: ["plan", "handoff", "final", "verdict", "risk", "interrupt", "test", "retry", "guardrail", "tool"],
  },
  { id: "Reasoning", kinds: ["thought", "action", "observation", "final"] },
  { id: "All", kinds: null },
];

/** One card. Only thoughts that just happened slide in; history renders still (no mass animation). */
const Item = memo(function Item({ t, agents, fresh }: { t: ThoughtItem; agents?: AgentInfo[]; fresh: boolean }) {
  const s = STYLE[t.kind];
  return (
    <li
      className={cn(
        "thought-card relative overflow-hidden rounded-lg border border-border bg-white/[0.02] px-3 py-2.5 transition-colors hover:border-white/15",
        fresh && "thought-in",
      )}
      style={{ "--kind": s.color } as React.CSSProperties}
    >
      <div className="flex items-center gap-2 text-[11px]">
        <span
          className="w-[76px] shrink-0 truncate rounded px-1.5 py-px text-center font-semibold"
          style={{ color: s.color, background: `color-mix(in srgb, ${s.color} 14%, transparent)` }}
        >
          {s.label}
        </span>
        {t.agent && <span className="truncate text-muted">{nameOf(t.agent, agents)}</span>}
        <span className="ml-auto font-mono text-[10px] text-faint">{new Date(t.ts * 1000).toLocaleTimeString()}</span>
      </div>
      <p
        className={cn(
          "mt-1.5 text-[13px] leading-snug text-text",
          t.ok === false && "text-[color-mix(in_srgb,var(--error)_80%,white)]",
        )}
      >
        {t.title}
      </p>
      {t.body && <p className="mt-1 line-clamp-3 text-xs leading-relaxed whitespace-pre-wrap text-muted">{t.body}</p>}
    </li>
  );
});

export function ThoughtStream({
  view,
  agents,
  className,
}: {
  view: MissionView;
  agents?: AgentInfo[];
  className?: string;
}) {
  const [filter, setFilter] = useState("Key steps");
  const [follow, setFollow] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  // thoughts older than the moment this panel opened are history: render them without animation
  const [openedAt] = useState(() => Date.now() / 1000);
  const items = useMemo(() => {
    const kinds = FILTERS.find((f) => f.id === filter)?.kinds;
    return (kinds ? view.thoughts.filter((t) => kinds.includes(t.kind)) : view.thoughts).slice(-150);
  }, [view.thoughts, filter]);

  useEffect(() => {
    const el = box.current;
    if (!follow || !el) return;
    // jump on first load, glide for live updates
    el.scrollTo({ top: el.scrollHeight, behavior: el.scrollTop === 0 ? "auto" : "smooth" });
  }, [items, follow]);

  return (
    <section
      className={cn("panel flex min-h-0 flex-col", className)}
      aria-label="Thought stream"
      data-tour="thought-stream"
    >
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <h2 className="panel-title text-sm">Activity</h2>
        <span className="ml-auto truncate font-mono text-[10px] text-faint">
          <CountUp value={String(view.llm.calls)} /> LLM calls ·{" "}
          <CountUp value={String(view.llm.prompt + view.llm.completion)} /> tokens
        </span>
      </header>
      <div className="flex gap-1 px-4 pt-2.5">
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
        className="min-h-0 flex-1 overflow-y-auto px-4 py-2.5"
      >
        {items.length === 0 ? (
          <p className="py-10 text-center text-sm text-faint">
            {filter === "All" || !view.thoughts.length
              ? "Steps appear here as the agents plan, act and check their work."
              : "No key steps yet. Choose All to see every event."}
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((t) => (
              <Item key={t.id} t={t} agents={agents} fresh={t.ts > openedAt} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
