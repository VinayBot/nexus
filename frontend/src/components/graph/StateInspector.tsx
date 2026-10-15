"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useState } from "react";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { MissionView } from "@/lib/missionView";

interface StateResponse {
  values: Record<string, unknown>;
  next: string[];
  checkpoint_id: string | null;
  interrupts: unknown[];
  tokens: { prompt: number; completion: number; calls: number; by_agent: Record<string, number> };
}

function preview(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (Array.isArray(v)) return `[${v.length}]`;
  if (typeof v === "object") return `{${Object.keys(v as object).length}}`;
  const s = String(v);
  return s.length > 60 ? `${s.slice(0, 60)}…` : s;
}

function JsonNode({ k, v, depth = 0 }: { k: string; v: unknown; depth?: number }) {
  const [open, setOpen] = useState(
    depth < 1 && typeof v === "object" && v !== null && Object.keys(v as object).length < 6,
  );
  const expandable = typeof v === "object" && v !== null;
  return (
    <li className="leading-snug">
      <button type="button" disabled={!expandable} onClick={() => setOpen((o) => !o)} className="text-left">
        <span className="text-accent/90">
          {expandable ? (open ? "▾ " : "▸ ") : "  "}
          {k}
        </span>
        <span className="text-faint">: {open ? "" : preview(v)}</span>
      </button>
      {open && expandable && (
        <ul className="ml-3 border-l border-border/40 pl-2">
          {Object.entries(v as Record<string, unknown>)
            .slice(0, 60)
            .map(([ck, cv]) => (
              <JsonNode key={ck} k={ck} v={cv} depth={depth + 1} />
            ))}
        </ul>
      )}
    </li>
  );
}

/** Live mission state with reducer-merge highlights and per-agent token bars. */
export function StateInspector({ view, reducers }: { view: MissionView; reducers: Record<string, string> }) {
  const lastCp = view.checkpoints[view.checkpoints.length - 1]?.id;
  const { data } = useQuery({
    queryKey: ["state", view.missionId, lastCp],
    queryFn: () => get<StateResponse>(`/missions/${view.missionId}/state`),
    enabled: Boolean(view.missionId),
    placeholderData: (prev) => prev,
  });
  const recentMerges = view.merges.slice(-8).reverse();
  const hotChannels = new Set(view.merges.slice(-6).map((m) => m.channel));
  const byAgent = Object.entries(data?.tokens.by_agent ?? view.llm.byAgent).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...byAgent.map(([, n]) => n));
  const values = data?.values ?? {};
  return (
    <aside
      className="flex w-[300px] shrink-0 flex-col border-l border-border/60 bg-black/30"
      aria-label="State inspector"
    >
      <header className="border-b border-border/50 px-3 py-2">
        <h3 className="panel-title text-sm text-gold">State Inspector</h3>
        <p className="font-mono text-[10px] text-faint">
          checkpoint {data?.checkpoint_id?.slice(-10) ?? "—"} · next: {data?.next.join(", ") || "—"}
        </p>
      </header>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-2 text-[11px]">
        <section>
          <h4 className="mb-1 text-[10px] tracking-wider text-faint uppercase">Reducer merges</h4>
          {recentMerges.length === 0 && <p className="text-faint">Parallel updates merge here.</p>}
          <ul className="space-y-1">
            {recentMerges.map((m) => (
              <motion.li
                key={m.seq}
                initial={{ backgroundColor: "rgba(79,227,240,0.25)" }}
                animate={{ backgroundColor: "rgba(79,227,240,0)" }}
                transition={{ duration: 2 }}
                className="rounded px-1.5 py-0.5"
              >
                <span className="text-accent">{m.channel}</span> <span className="text-faint">⟵ {m.reducer}</span>{" "}
                <span className="text-muted">
                  +{m.added} → {m.total}
                </span>
                {m.node && <span className="text-faint"> · {m.node}</span>}
              </motion.li>
            ))}
          </ul>
        </section>
        <section>
          <h4 className="mb-1 text-[10px] tracking-wider text-faint uppercase">Token budget by agent</h4>
          <ul className="space-y-1">
            {byAgent.slice(0, 8).map(([agent, n]) => (
              <li key={agent}>
                <div className="flex justify-between">
                  <span className="text-muted">{agent}</span>
                  <span className="font-mono text-faint">{n.toLocaleString()}</span>
                </div>
                <div className="mt-0.5 h-1.5 rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[var(--sun-gold)] to-[var(--ember)]"
                    style={{ width: `${(n / max) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h4 className="mb-1 text-[10px] tracking-wider text-faint uppercase">State (live)</h4>
          <ul className="font-mono">
            {Object.entries(values).map(([k, v]) => (
              <div
                key={k}
                className={cn("rounded", hotChannels.has(k) && "bg-accent/10 ring-1 ring-accent/40")}
                title={reducers[k] ? `reducer: ${reducers[k]}` : "last-write-wins"}
              >
                <JsonNode k={reducers[k] ? `${k} ⟵${reducers[k]}` : k} v={v} />
              </div>
            ))}
          </ul>
        </section>
      </div>
    </aside>
  );
}
