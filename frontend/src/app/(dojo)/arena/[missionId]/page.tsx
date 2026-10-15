"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import dynamic from "next/dynamic";
import { use, useMemo, useState } from "react";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { avatarOf, nameOf, useAgents } from "@/lib/agents";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initialRobot, settle } from "@/lib/robotMachine";
import { useMissionStream, useNow } from "@/stores/missionStream";

const DiffEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.DiffEditor), {
  ssr: false,
  loading: () => <p className="p-4 text-xs text-faint">Loading Monaco…</p>,
});

interface Proposal {
  solver_id: string;
  strategy: string;
  content: string;
  rationale: string;
  patch: { file: string; search: string; replace: string } | null;
  tests: { ok: boolean; passed: number; failed: number; errors: number; summary?: string } | null;
  round: number;
}

/** Hakari's balance: tilts toward the winner once the verdict lands. */
function Scale({ tilt }: { tilt: number }) {
  return (
    <svg viewBox="0 0 120 70" className="w-40">
      <rect x={58} y={14} width={4} height={50} fill="#d9c38a" />
      <rect x={40} y={62} width={40} height={5} rx={2} fill="#8e6a3c" />
      <motion.g
        animate={{ rotate: tilt }}
        transition={{ type: "spring", stiffness: 50, damping: 8 }}
        style={{ transformOrigin: "60px 14px" }}
      >
        <rect x={10} y={12} width={100} height={4} rx={2} fill="#d9c38a" />
        <path d="M14,16 l-8,20 h16 Z M106,16 l-8,20 h16 Z" fill="#d9c38a" opacity={0.85} />
      </motion.g>
      <circle cx={60} cy={14} r={4} fill="#c8341f" />
    </svg>
  );
}

function Sparks() {
  return (
    <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" aria-hidden>
      {Array.from({ length: 10 }, (_, i) => (
        <motion.span
          key={i}
          className="absolute block h-0.5 w-4 rounded bg-[var(--sun-core)]"
          initial={{ opacity: 1, x: 0, y: 0, rotate: i * 36 }}
          animate={{ opacity: 0, x: Math.cos((i * Math.PI) / 5) * 60, y: Math.sin((i * Math.PI) / 5) * 60 }}
          transition={{ duration: 0.8, repeat: Infinity, repeatDelay: 1.2 }}
        />
      ))}
    </div>
  );
}

export default function Page({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = use(params);
  const view = useMissionStream(missionId);
  const agents = useAgents();
  const now = useNow(1000);
  const council = view.council;
  const lastCp = view.checkpoints[view.checkpoints.length - 1]?.id;
  const state = useQuery({
    queryKey: ["state", missionId, lastCp, "arena"],
    queryFn: () =>
      get<{ values: { proposals?: Record<string, Proposal>; verdict?: Record<string, unknown> } }>(
        `/missions/${missionId}/state`,
      ),
  });
  const [open, setOpen] = useState<string | null>(null);
  const solvers = Object.keys(council.proposals).length
    ? Object.keys(council.proposals)
    : Object.keys(state.data?.values.proposals ?? {});
  const proposals = state.data?.values.proposals ?? {};
  const verdict = council.verdict;
  const masked = council.labels.length > 0 && !verdict;

  const byLabel = useMemo(() => {
    const out: Record<string, number[]> = {};
    council.reviews.forEach((r) => (out[r.target_label] ??= []).push(r.score));
    return out;
  }, [council.reviews]);
  const winnerIdx = verdict ? solvers.indexOf(verdict.winner) : -1;
  const tilt = winnerIdx < 0 ? 0 : winnerIdx < solvers.length / 2 ? -14 : 14;

  if (!solvers.length) {
    return (
      <>
        <PageHeader title="Council Arena" kanji="闘技" />
        <EmptyState title="No tournament in this mission yet">
          The arena fills when a council or solution tournament begins (Council Q&A, Self-Healing, Ticket Solver).
        </EmptyState>
      </>
    );
  }
  return (
    <>
      <RobotDefs />
      <PageHeader
        title="Council Arena"
        kanji="闘技"
        description="Solvers propose independently (same model, different strategy and temperature), code patches are proven in their own sandboxes, proposals are masked as A/B/C for peer review, disagreement triggers debate, and the Judge weighs evidence first."
      />
      <section className="panel relative overflow-hidden p-4" data-tour="arena">
        <div className="mx-auto flex max-w-5xl flex-col items-center">
          <div className="flex items-center gap-4">
            <Robot
              avatar={avatarOf("hakari", agents.data)}
              state={settle(view.robots.hakari ?? initialRobot(0), now)}
              label="Hakari · Judge"
              size={70}
            />
            <Scale tilt={tilt} />
            <Robot
              avatar={avatarOf("kiri", agents.data)}
              state={settle(view.robots.kiri ?? initialRobot(0), now)}
              label="Kiri · Critic"
              size={64}
            />
          </div>
          <div
            className="relative mt-4 grid w-full gap-4 rounded-[50%] border-2 border-dashed border-gold/30 bg-[radial-gradient(ellipse_at_center,rgba(200,52,31,0.15),transparent_70%)] px-10 py-10"
            style={{ gridTemplateColumns: `repeat(${solvers.length}, minmax(0, 1fr))` }}
          >
            {council.rounds.some((r) => !r.converged) && !verdict && <Sparks />}
            {solvers.map((sid) => {
              const p = council.proposals[sid] ?? {
                strategy: proposals[sid]?.strategy ?? "",
                summary: proposals[sid]?.content ?? "",
                revised: false,
              };
              const t = council.tests[sid] ?? proposals[sid]?.tests;
              const isWinner = verdict?.winner === sid;
              const isRunnerUp = verdict?.runner_up === sid;
              return (
                <div key={sid} className="flex flex-col items-center gap-2">
                  <div className="relative">
                    {sid === "fix_library" ? (
                      <div
                        className="grid size-20 place-items-center rounded-full border border-[#b8a7ff]/60 bg-[#b8a7ff]/10 text-3xl"
                        title="Remembered fix from the Fix Library"
                      >
                        📚
                      </div>
                    ) : (
                      <Robot
                        avatar={avatarOf(sid, agents.data)}
                        state={settle(view.robots[sid] ?? initialRobot(0), now)}
                        size={76}
                        showBubble={false}
                      />
                    )}
                    <AnimatePresence>
                      {masked && (
                        <motion.div
                          initial={{ y: -60, opacity: 0, rotate: -20 }}
                          animate={{ y: 0, opacity: 1, rotate: 0 }}
                          exit={{ y: -40, opacity: 0 }}
                          className="absolute top-[18%] left-1/2 grid h-8 w-14 -translate-x-1/2 place-items-center rounded-[40%] bg-[#f5f2ec] font-display text-xs font-bold text-[#8e1b17] shadow-lg"
                        >
                          ?
                        </motion.div>
                      )}
                    </AnimatePresence>
                    {isWinner && (
                      <motion.span
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute -top-3 left-1/2 -translate-x-1/2 rounded bg-[var(--sun-gold)] px-2 text-[10px] font-bold text-[var(--ink)]"
                      >
                        WINNER {verdict?.winner_label}
                      </motion.span>
                    )}
                  </div>
                  <span className="text-xs">{nameOf(sid, agents.data)}</span>
                  <span className="text-[10px] text-gold">{p.strategy}</span>
                  <motion.button
                    type="button"
                    onClick={() => setOpen(sid)}
                    initial={{ scaleX: 0.2, opacity: 0 }}
                    animate={{ scaleX: 1, opacity: 1 }}
                    className={cn(
                      "w-full rounded-md bg-[linear-gradient(180deg,#efe2c4,#e3d1aa)] p-2 text-left text-[11px] text-[#3b2410]",
                      isWinner && "ring-2 ring-[var(--sun-gold)]",
                      isRunnerUp && "ring-1 ring-[#2f8fbf]",
                    )}
                  >
                    <span className="line-clamp-4">
                      {p.revised ? "(revised) " : ""}
                      {p.summary}
                    </span>
                  </motion.button>
                  {t && (
                    <span className="flex items-center gap-1 text-[10px]">
                      <span
                        className="block h-4 w-3 rounded-[45%]"
                        style={{
                          background: t.ok ? "var(--success)" : "var(--error)",
                          boxShadow: `0 0 10px ${t.ok ? "var(--success)" : "var(--error)"}`,
                        }}
                      />
                      {t.passed}✓ {t.failed + t.errors}✗
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        {verdict && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="mx-auto mt-4 max-w-3xl rounded-xl border border-gold/50 bg-black/40 p-3 text-center"
          >
            <p className="font-display text-lg text-[var(--sun-core)]">
              {nameOf(verdict.winner, agents.data)} wins as {verdict.winner_label} · confidence {verdict.confidence}
              {verdict.escalate && <span className="ml-2 text-sm text-danger">→ escalated to a human</span>}
            </p>
            <p className="mt-1 text-xs text-muted">Dissent: {verdict.dissent}</p>
            {verdict.runner_up && (
              <p className="text-[11px] text-[#7fc4e6]">
                Runner-up remembered: {nameOf(verdict.runner_up, agents.data)} (fork it in the Scroll of Time)
              </p>
            )}
          </motion.div>
        )}
      </section>

      <div className="mt-3 grid gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
        <section className="panel p-3">
          <h2 className="panel-title text-sm text-gold">Anonymous peer review</h2>
          <ul className="mt-2 space-y-2">
            {Object.entries(byLabel).map(([label, scores]) => {
              const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
              return (
                <li key={label} className="text-xs">
                  <div className="flex justify-between">
                    <span>Proposal {label}</span>
                    <span className="font-mono">
                      {mean.toFixed(1)} · {scores.length} reviews
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-white/5">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-[var(--sun-gold)] to-[var(--ember)]"
                      animate={{ width: `${mean * 10}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
          <ul className="mt-3 max-h-60 space-y-1 overflow-y-auto">
            {council.reviews
              .slice(-20)
              .reverse()
              .map((r, i) => (
                <motion.li
                  key={`${r.reviewer}-${r.target_label}-${i}`}
                  initial={{ x: 30, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  className="text-[11px] text-muted"
                >
                  <span className="text-text">{nameOf(r.reviewer, agents.data)}</span> → {r.target_label}:{" "}
                  <span className="font-mono text-gold">{r.score.toFixed(1)}</span> — {r.reason}
                </motion.li>
              ))}
          </ul>
          {council.rounds.length > 0 && (
            <p className="mt-2 text-[11px] text-faint">
              Rounds:{" "}
              {council.rounds
                .map((r) => `#${r.round} divergence ${r.divergence}${r.converged ? " ✓" : " ⚔"}`)
                .join(" · ")}
            </p>
          )}
        </section>
        <section className="panel min-h-[360px] p-3">
          <h2 className="panel-title text-sm text-gold">
            {open ? `Proposal by ${nameOf(open, agents.data)}` : "Open a scroll to read the proposal"}
          </h2>
          {open &&
            proposals[open] &&
            (proposals[open].patch ? (
              <div className="mt-2 h-72 overflow-hidden rounded-lg border border-border">
                <DiffEditor
                  original={proposals[open].patch!.search}
                  modified={proposals[open].patch!.replace}
                  language="python"
                  theme="vs-dark"
                  options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, fontSize: 12 }}
                />
              </div>
            ) : (
              <p className="mt-2 text-sm whitespace-pre-wrap">{proposals[open].content}</p>
            ))}
          {open && proposals[open] && <p className="mt-2 text-xs text-muted">Rationale: {proposals[open].rationale}</p>}
          {open && proposals[open]?.tests && (
            <p className="mt-1 font-mono text-[11px] text-faint">{proposals[open].tests!.summary}</p>
          )}
        </section>
      </div>
    </>
  );
}
