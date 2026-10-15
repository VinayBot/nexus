"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { nameOf, useAgents } from "@/lib/agents";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useActiveMission } from "@/stores/missions";
import { useMissionStream, useStreams } from "@/stores/missionStream";

interface Point {
  id: string;
  collection: string;
  title: string;
  x: number;
  y: number;
}
interface Hit {
  id: string;
  collection: string;
  title: string;
  text: string;
  score: number;
}
interface Item {
  id: string;
  title: string;
  text: string;
  metadata: Record<string, unknown>;
}

const SHELF_COLOR: Record<string, string> = {
  fix_library: "#c8341f",
  missions: "#f7a440",
  docs: "#4fe3f0",
  lessons: "#3fd18b",
};

function Vessel({ name, used, budget, pruned }: { name: string; used: number; budget: number; pruned: boolean }) {
  const pct = Math.min(1, used / Math.max(1, budget));
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative h-28 w-16 overflow-hidden rounded-b-[28px] rounded-t-lg border-2 border-border-strong bg-black/40">
        <motion.div
          className="absolute inset-x-0 bottom-0"
          animate={{ height: `${pct * 100}%` }}
          transition={{ type: "spring", stiffness: 60, damping: 14 }}
          style={{
            background: pct > 0.85 ? "linear-gradient(0deg,#c8341f,#f2662a)" : "linear-gradient(0deg,#1b6f8a,#4fe3f0)",
          }}
        />
        <div
          className="absolute inset-x-0 border-t border-dashed border-danger/70"
          style={{ bottom: "85%" }}
          title="budget line"
        />
        <AnimatePresence>
          {pruned && (
            <motion.span
              initial={{ y: 0, opacity: 1 }}
              animate={{ y: -30, opacity: 0 }}
              exit={{ opacity: 0 }}
              className="absolute top-2 left-1/2 -translate-x-1/2 text-xs"
            >
              📜
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <span className="text-[11px]">{name}</span>
      <span className="font-mono text-[10px] text-faint">
        {used.toLocaleString()} / {budget.toLocaleString()}
      </span>
    </div>
  );
}

export default function Page() {
  const activeId = useActiveMission((s) => s.activeId);
  const view = useMissionStream(activeId);
  const events = useStreams((s) => (activeId ? s.events[activeId] : undefined));
  const agents = useAgents();
  const stats = useQuery({
    queryKey: ["memory-stats"],
    queryFn: () => get<{ collections: Record<string, number>; embedding_ok: boolean }>("/memory/stats"),
    refetchInterval: 15_000,
  });
  const map = useQuery({
    queryKey: ["memory-map", stats.data?.collections],
    queryFn: () => get<Point[]>("/memory/map"),
  });
  const [shelf, setShelf] = useState<string | null>("fix_library");
  const items = useQuery({
    queryKey: ["shelf", shelf],
    queryFn: () => get<Item[]>(`/memory/collections/${shelf}?limit=40`),
    enabled: Boolean(shelf),
  });
  const [book, setBook] = useState<Item | null>(null);
  const [q, setQ] = useState("");
  const search = useQuery({
    queryKey: ["memory-search", q],
    queryFn: () => get<Hit[]>(`/memory/search?q=${encodeURIComponent(q)}&k=8`),
    enabled: q.length > 2,
  });

  const vessels = useMemo(() => {
    const last: Record<string, number> = {};
    for (const e of events ?? [])
      if (e.type === "llm.call" && e.payload.agent_id) last[e.payload.agent_id] = e.payload.prompt_tokens;
    return Object.entries(last).map(([id, used]) => {
      const spec = agents.data?.find((a) => a.id === id);
      return { id, used, budget: (spec?.num_ctx ?? 4096) - 768 };
    });
  }, [events, agents.data]);
  const lastPrune = view.memory.filter((m) => m.kind === "pruned" || m.kind === "summarised").slice(-1)[0];
  const recalled = new Set((search.data ?? []).map((h) => h.id));

  return (
    <>
      <PageHeader
        title="Memory Palace"
        kanji="記憶"
        description="Short-term memory is each agent's context window — pruned by sliding window or folded into a rolling summary when it nears the budget. Long-term memory lives in ChromaDB: the Fix Library, past missions, project docs and lessons."
      />
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel p-4">
          <h2 className="panel-title text-sm text-gold">
            Context vessels {activeId ? `· mission ${activeId}` : "(select a mission in the top bar)"}
          </h2>
          {vessels.length === 0 ? (
            <p className="mt-3 text-xs text-faint">
              Each agent&apos;s last prompt size fills its vessel as it works. Run a mission to watch them rise and get
              pruned.
            </p>
          ) : (
            <div className="mt-3 flex flex-wrap gap-5">
              {vessels.map((v) => (
                <Vessel
                  key={v.id}
                  name={nameOf(v.id, agents.data)}
                  used={v.used}
                  budget={v.budget}
                  pruned={lastPrune?.agent === v.id}
                />
              ))}
            </div>
          )}
          <h3 className="mt-4 text-[10px] tracking-wider text-faint uppercase">Pruning events</h3>
          <ul className="mt-1 space-y-1 text-xs">
            {view.memory
              .filter((m) => m.before !== undefined)
              .slice(-8)
              .reverse()
              .map((m, i) => (
                <motion.li
                  key={`${m.ts}-${i}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-2"
                >
                  <span className="chip">{m.kind === "summarised" ? "folded into summary" : m.detail}</span>
                  <span className="text-muted">{m.agent ? nameOf(m.agent, agents.data) : ""}</span>
                  <span className="font-mono text-faint">
                    {m.before} → {m.after} tokens
                  </span>
                </motion.li>
              ))}
            {view.memory.filter((m) => m.before !== undefined).length === 0 && (
              <li className="text-faint">No pruning yet in this mission (prompts stayed under budget).</li>
            )}
          </ul>
          <div className="mt-4 rounded-lg border border-border/50 p-3">
            <p className="text-[11px] text-muted">
              How the window works — system prompt and pinned items (task, plan, current step) always stay; the oldest
              turns drop first; with <em>summarise</em> they fold into one pinned summary scroll:
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1 text-[10px]">
              <span className="rounded bg-accent/20 px-2 py-1 text-accent">system 📌</span>
              <span className="rounded bg-accent/20 px-2 py-1 text-accent">task 📌</span>
              <span className="rounded bg-[#e9d8a6]/20 px-2 py-1 text-[#e9d8a6]">summary 📜</span>
              {[1, 2, 3, 4, 5].map((n) => (
                <span
                  key={n}
                  className={cn(
                    "rounded px-2 py-1",
                    n <= 2 ? "bg-white/5 text-faint line-through" : "bg-white/10 text-text",
                  )}
                >
                  turn {n}
                </span>
              ))}
              <span className="ml-1 rounded border border-dashed border-gold px-2 py-0.5 text-gold">← window →</span>
            </div>
          </div>
        </section>

        <section className="panel p-4">
          <h2 className="panel-title text-sm text-gold">Embedding map</h2>
          <p className="text-[11px] text-faint">
            PCA of every stored vector (computed server-side). Search to make recalled memories glow.
            {!stats.data?.embedding_ok && " Embedding model unavailable — keyword fallback."}
          </p>
          <svg viewBox="-1.15 -1.15 2.3 2.3" className="mt-2 aspect-square w-full rounded-lg bg-black/40">
            {map.data?.map((p) => (
              <circle
                key={p.id}
                cx={p.x}
                cy={p.y}
                r={recalled.has(p.id) ? 0.045 : 0.025}
                fill={SHELF_COLOR[p.collection] ?? "#aaa"}
                opacity={recalled.size && !recalled.has(p.id) ? 0.3 : 0.9}
                style={recalled.has(p.id) ? { filter: "drop-shadow(0 0 0.04px white)" } : undefined}
              >
                <title>{`${p.collection}: ${p.title}`}</title>
              </circle>
            ))}
          </svg>
          <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
            {Object.entries(SHELF_COLOR).map(([k, c]) => (
              <span key={k} className="chip">
                <span className="size-2 rounded-full" style={{ background: c }} /> {k} (
                {stats.data?.collections[k] ?? 0})
              </span>
            ))}
          </div>
        </section>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel p-4">
          <h2 className="panel-title text-sm text-gold">Library</h2>
          <div className="mt-2 space-y-3">
            {Object.entries(stats.data?.collections ?? {}).map(([name, n]) => (
              <div key={name}>
                <button
                  type="button"
                  onClick={() => setShelf(name)}
                  className={cn("text-xs", shelf === name ? "text-gold" : "text-muted")}
                >
                  {name} · {n}
                </button>
                <div className="mt-1 flex h-16 items-end gap-0.5 border-b-4 border-[#5a3a1a] px-1">
                  {(shelf === name
                    ? (items.data ?? [])
                    : Array.from({ length: Math.min(n, 30) }, (_, i) => ({
                        id: `${name}-${i}`,
                        title: "",
                        text: "",
                        metadata: {},
                      }))
                  )
                    .slice(0, 40)
                    .map((it, i) => (
                      <motion.button
                        key={it.id}
                        type="button"
                        whileHover={{ y: -6 }}
                        onClick={() => shelf === name && setBook(it as Item)}
                        title={(it as Item).title}
                        className="w-3 rounded-t-sm"
                        style={{
                          height: `${40 + ((i * 37) % 24)}px`,
                          background: SHELF_COLOR[name] ?? "#888",
                          opacity: 0.55 + ((i * 13) % 40) / 100,
                        }}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
          {book && (
            <div className="mt-3 rounded-lg bg-[linear-gradient(180deg,#efe2c4,#e3d1aa)] p-3 text-[#3b2410]">
              <div className="flex">
                <p className="font-display text-sm">{book.title}</p>
                <button type="button" className="ml-auto text-xs" onClick={() => setBook(null)}>
                  close
                </button>
              </div>
              <pre className="mt-1 max-h-60 overflow-auto font-mono text-[10.5px] whitespace-pre-wrap">{book.text}</pre>
            </div>
          )}
        </section>
        <section className="panel p-4">
          <h2 className="panel-title text-sm text-gold">Semantic search</h2>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. guest orders crash on email"
            className="mt-2 w-full rounded-lg border border-border bg-black/40 px-3 py-2 text-sm"
            aria-label="Search memory"
          />
          <ul className="mt-2 max-h-80 space-y-1.5 overflow-y-auto">
            {search.data?.map((h) => (
              <li key={h.id} className="rounded border border-border/40 p-2 text-xs">
                <div className="flex gap-2">
                  <span className="chip" style={{ color: SHELF_COLOR[h.collection] }}>
                    {h.collection}
                  </span>
                  <span className="truncate">{h.title}</span>
                  <span className="ml-auto font-mono text-faint">{h.score.toFixed(2)}</span>
                </div>
                <p className="mt-1 line-clamp-3 text-muted">{h.text}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
