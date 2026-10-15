"use client";

import { AnimatePresence, motion } from "motion/react";
import { useMemo, useRef } from "react";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { avatarOf, nameOf, type AgentInfo } from "@/lib/agents";
import type { MissionView } from "@/lib/missionView";
import { initialRobot, settle } from "@/lib/robotMachine";
import { cn } from "@/lib/cn";
import { useNow } from "@/stores/missionStream";
import { DojoScene } from "./DojoScene";
import { ARMORY, LANTERNS, POSTS, postOf } from "./layout";

const CLAN = Object.keys(POSTS);

/** A glowing scroll that flies in an arc from the Shogun to the worker on `handoff`. */
function FlyingScroll({ to, onDone }: { to: { x: number; y: number }; onDone: () => void }) {
  const from = POSTS.shogun!;
  const midY = Math.min(from.y, to.y) - 18;
  return (
    <motion.div
      className="pointer-events-none absolute z-20"
      initial={{ left: `${from.x}%`, top: `${from.y}%`, opacity: 0, rotate: 0 }}
      animate={{
        left: [`${from.x}%`, `${(from.x + to.x) / 2}%`, `${to.x}%`],
        top: [`${from.y}%`, `${midY}%`, `${to.y}%`],
        opacity: [0, 1, 1, 0],
        rotate: [0, 200, 360],
      }}
      transition={{ duration: 1.1, ease: "easeInOut" }}
      onAnimationComplete={onDone}
    >
      <div className="h-3 w-7 -translate-x-1/2 rounded-sm border border-[#a3793f] bg-[#f3e3c3] shadow-[0_0_14px_rgba(79,227,240,0.9)]" />
    </motion.div>
  );
}

function Petals() {
  const petals = Array.from({ length: 18 }, (_, i) => i);
  return (
    <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden" aria-hidden>
      {petals.map((i) => (
        <motion.span
          key={i}
          className="absolute size-2.5 rounded-[60%_10%] bg-[#ffc4ce]"
          initial={{ left: `${50 + (i % 2 ? 1 : -1) * 3}%`, top: "30%", opacity: 1, rotate: 0 }}
          animate={{ left: `${8 + ((i * 53) % 84)}%`, top: `${70 + ((i * 17) % 28)}%`, opacity: 0, rotate: 540 }}
          transition={{ duration: 2.4 + (i % 5) * 0.2, ease: "easeOut" }}
        />
      ))}
    </div>
  );
}

export function DojoFloor({
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
    const ids = new Set(CLAN);
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
      <DojoScene />

      {/* tool-call beams to the Armory */}
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
              x2={ARMORY.x + 4}
              y2={ARMORY.y}
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
            <Robot
              avatar={avatarOf(id, agents)}
              state={state}
              isShogun={id === "shogun"}
              label={nameOf(id, agents)}
              size={id === "shogun" ? 92 : 70}
            />
          </motion.div>
        );
      })}

      {/* scrolls flying on handoffs (Send fan-out = several at once) */}
      <AnimatePresence>
        {flying.map((h) => (
          <FlyingScroll key={h.seq} to={postOf(h.target)} onDone={() => done.current.add(h.seq)} />
        ))}
      </AnimatePresence>

      {/* sandbox test lanterns */}
      {tests.length > 0 && (
        <div
          className="absolute z-20 flex -translate-x-1/2 gap-3"
          style={{ left: `${LANTERNS.x}%`, top: `${LANTERNS.y}%` }}
        >
          {tests.map(([target, t]) => (
            <div
              key={target}
              className="flex flex-col items-center gap-0.5"
              title={`${target}: ${t.passed} passed, ${t.failed + t.errors} failed`}
            >
              <motion.span
                className="block h-5 w-4 rounded-[45%]"
                initial={{ scale: 0.4, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                style={{
                  background: t.ok ? "var(--success)" : "var(--error)",
                  boxShadow: `0 0 14px ${t.ok ? "var(--success)" : "var(--error)"}`,
                }}
              />
              <span className="text-[9px] text-muted">{target.replace("ronin_", "R-")}</span>
            </div>
          ))}
        </div>
      )}

      {/* waiting for the human: red lantern by the dais */}
      {waiting && (
        <div className="absolute z-20 flex items-center gap-2" style={{ left: "58%", top: "8%" }}>
          <span className="animate-alarm block h-6 w-5 rounded-[45%] bg-danger shadow-[0_0_18px_var(--error)]" />
          <span className="rounded-full bg-black/50 px-2 py-0.5 text-xs text-text">Awaiting your seal</span>
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

      {celebrating && <Petals key={view.lastSeq} />}
    </div>
  );
}
