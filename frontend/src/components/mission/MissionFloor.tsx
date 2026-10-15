"use client";

import { AnimatePresence, motion } from "motion/react";
import { useMemo, useRef } from "react";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { avatarOf, nameOf, type AgentInfo } from "@/lib/agents";
import type { MissionView } from "@/lib/missionView";
import { initialRobot, settle } from "@/lib/robotMachine";
import { cn } from "@/lib/cn";
import { useNow } from "@/stores/missionStream";
import { CommandDeck } from "./CommandDeck";
import { TOOLS, TEST_BAY, POSTS, postOf } from "./layout";

const SQUAD = Object.keys(POSTS);

/** A glowing data orb that arcs from the Commander to the worker on `handoff`, trailing light. */
function DataOrb({ to, onDone }: { to: { x: number; y: number }; onDone: () => void }) {
  const from = POSTS.commander!;
  const midY = Math.min(from.y, to.y) - 18;
  const path = {
    left: [`${from.x}%`, `${(from.x + to.x) / 2}%`, `${to.x}%`],
    top: [`${from.y}%`, `${midY}%`, `${to.y}%`],
  };
  return (
    <>
      {[0.12, 0.06].map((lag, i) => (
        <motion.div
          key={i}
          className="pointer-events-none absolute z-20"
          initial={{ left: `${from.x}%`, top: `${from.y}%`, opacity: 0 }}
          animate={{ ...path, opacity: [0, 0.5 - i * 0.2, 0] }}
          transition={{ duration: 1.1, ease: "easeInOut", delay: lag }}
        >
          <div className="size-2 -translate-x-1/2 rounded-full bg-accent blur-[2px]" />
        </motion.div>
      ))}
      <motion.div
        className="pointer-events-none absolute z-20"
        initial={{ left: `${from.x}%`, top: `${from.y}%`, opacity: 0, scale: 0.4 }}
        animate={{ ...path, opacity: [0, 1, 1, 0], scale: [0.4, 1.2, 1, 1.8] }}
        transition={{ duration: 1.1, ease: "easeInOut" }}
        onAnimationComplete={onDone}
      >
        <div className="relative size-3.5 -translate-x-1/2 rounded-full bg-white shadow-[0_0_10px_3px_var(--cyan),0_0_26px_8px_rgba(79,227,240,0.5)]">
          <span className="absolute -inset-1.5 animate-spin rounded-full border border-dashed border-accent/80" />
        </div>
      </motion.div>
    </>
  );
}

/** Mission success: shockwave rings and light shards bursting from the Commander. */
function VictoryBurst() {
  const shards = Array.from({ length: 22 }, (_, i) => i);
  const c = POSTS.commander!;
  return (
    <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden" aria-hidden>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={`ring-${i}`}
          className="absolute size-24 -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
          style={{ left: `${c.x}%`, top: `${c.y}%`, borderColor: i === 1 ? "var(--cyan)" : "var(--sun-gold)" }}
          initial={{ scale: 0.2, opacity: 1 }}
          animate={{ scale: 9, opacity: 0 }}
          transition={{ duration: 1.6, delay: i * 0.25, ease: "easeOut" }}
        />
      ))}
      {shards.map((i) => {
        const a = (i / shards.length) * Math.PI * 2;
        return (
          <motion.span
            key={i}
            className="absolute h-1 w-4 rounded-full"
            style={{
              background: i % 3 === 0 ? "var(--cyan)" : i % 3 === 1 ? "var(--sun-core)" : "var(--jade)",
              boxShadow: "0 0 8px currentColor",
              rotate: `${(a * 180) / Math.PI}deg`,
            }}
            initial={{ left: `${c.x}%`, top: `${c.y}%`, opacity: 1 }}
            animate={{ left: `${c.x + Math.cos(a) * 45}%`, top: `${c.y + Math.sin(a) * 70}%`, opacity: 0 }}
            transition={{ duration: 1.8 + (i % 4) * 0.2, ease: "easeOut" }}
          />
        );
      })}
      <motion.div
        className="absolute inset-x-0 top-[38%] text-center font-display text-3xl font-bold tracking-[0.3em] text-[var(--jade)]"
        style={{ textShadow: "0 0 18px var(--jade)" }}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: [0, 1, 1, 0], scale: [0.6, 1.05, 1, 1.1] }}
        transition={{ duration: 2.6, times: [0, 0.2, 0.75, 1] }}
      >
        MISSION COMPLETE
      </motion.div>
    </div>
  );
}

export function MissionFloor({
  view,
  agents,
  className,
}: {
  view: MissionView;
  agents?: AgentInfo[];
  className?: string;
}) {
  const now = useNow(1000);
  const done = useRef(new Set<number>());
  const baseline = useRef<number | null>(null);
  if (baseline.current === null) baseline.current = view.lastSeq; // don't replay old handoffs on mount

  const present = useMemo(() => {
    const ids = new Set(SQUAD);
    Object.keys(view.robots).forEach((id) => ids.add(id));
    return [...ids];
  }, [view.robots]);

  const flying = view.handoffs.filter((h) => h.seq > (baseline.current ?? 0) && !done.current.has(h.seq)).slice(-6);
  const beams = Object.entries(view.toolCalls)
    .filter(([, c]) => !c.done && c.agent)
    .slice(-6);
  const tests = Object.entries(view.council.tests);
  const celebrating = view.status === "completed" && view.outcome === "success";
  const waiting = view.status === "paused";

  return (
    <div className={cn("relative overflow-hidden rounded-2xl border border-border bg-[#120806]", className)}>
      <RobotDefs />
      <CommandDeck />

      {/* tool-call beams to the Tools */}
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 z-10 h-full w-full"
        aria-hidden
      >
        {beams.map(([id, c]) => {
          const p = postOf(c.agent!);
          return (
            <line
              key={id}
              x1={p.x}
              y1={p.y + 6}
              x2={TOOLS.x + 4}
              y2={TOOLS.y}
              stroke="var(--cyan)"
              strokeWidth={0.5}
              className="animate-flow"
              vectorEffect="non-scaling-stroke"
              style={{ filter: "drop-shadow(0 0 3px var(--cyan))" }}
            />
          );
        })}
      </svg>

      {/* robots */}
      {present.map((id, i) => {
        const post = postOf(id, i);
        const state = settle(view.robots[id] ?? initialRobot(0), now);
        const idle = !view.robots[id];
        return (
          <motion.div
            key={id}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${post.x}%`, top: `${post.y}%`, zIndex: (post.z ?? 1) + Math.round(post.y / 10) }}
            animate={{ opacity: idle ? 0.55 : 1, filter: idle ? "saturate(0.6)" : "saturate(1)" }}
          >
            {!idle && (
              <motion.span
                className="pointer-events-none absolute top-1/2 left-1/2 size-16 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent"
                initial={{ scale: 0.2, opacity: 0.9 }}
                animate={{ scale: 2.4, opacity: 0 }}
                transition={{ duration: 0.9, ease: "easeOut" }}
                aria-hidden
              />
            )}
            <Robot
              avatar={avatarOf(id, agents)}
              state={state}
              isCommander={id === "commander"}
              label={nameOf(id, agents)}
              size={id === "commander" ? 92 : 70}
            />
          </motion.div>
        );
      })}

      {/* data orbs flying on handoffs (Send fan-out = several at once) */}
      <AnimatePresence>
        {flying.map((h) => (
          <DataOrb key={h.seq} to={postOf(h.target)} onDone={() => done.current.add(h.seq)} />
        ))}
      </AnimatePresence>

      {/* sandbox test light bars */}
      {tests.length > 0 && (
        <div
          className="absolute z-20 flex -translate-x-1/2 gap-3"
          style={{ left: `${TEST_BAY.x}%`, top: `${TEST_BAY.y}%` }}
        >
          {tests.map(([target, t]) => {
            const color = t.ok ? "var(--success)" : "var(--error)";
            return (
              <div
                key={target}
                className="flex flex-col items-center gap-0.5"
                title={`${target}: ${t.passed} passed, ${t.failed + t.errors} failed`}
              >
                <motion.span
                  className="block h-6 w-2 origin-bottom rounded-full"
                  initial={{ scaleY: 0, opacity: 0 }}
                  animate={{ scaleY: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 14 }}
                  style={{ background: color, boxShadow: `0 0 14px ${color}` }}
                />
                <span className="text-[9px] text-muted">{nameOf(target, agents)}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* waiting for the human: red beacon by the platform */}
      {waiting && (
        <div className="absolute z-20 flex items-center gap-2" style={{ left: "58%", top: "8%" }}>
          <span className="relative block size-4">
            <span className="absolute inset-0 animate-ping rounded-full bg-danger" />
            <span className="relative block size-4 rounded-full bg-danger shadow-[0_0_18px_var(--error)]" />
          </span>
          <span className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-text">Awaiting your approval</span>
        </div>
      )}

      {view.fanouts.length > 0 && view.status === "running" && (
        <div
          className="absolute z-20 rounded-full border border-accent/50 bg-black/50 px-2 py-0.5 text-[11px] text-accent"
          style={{ left: "56%", top: "14%" }}
        >
          Send ×{view.fanouts[view.fanouts.length - 1]!.count}
        </div>
      )}

      {celebrating && <VictoryBurst key={view.lastSeq} />}
    </div>
  );
}
