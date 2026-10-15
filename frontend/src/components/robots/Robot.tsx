"use client";

import { motion, type TargetAndTransition, type Transition } from "motion/react";
import { memo } from "react";
import type { RobotMode, RobotState } from "@/lib/robotMachine";
import { Eyes } from "./Eyes";
import { Prop, ShogunRegalia } from "./Props";

export interface Avatar {
  color: string;
  headband: string;
  prop: string;
  size?: "small" | "normal" | "large";
}

/** Shared SVG defs (gradients, glow filters); render once per page. */
export function RobotDefs() {
  return (
    <svg width={0} height={0} className="absolute" aria-hidden>
      <defs>
        <linearGradient id="nexus-shell" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="#f5f2ec" />
          <stop offset="100%" stopColor="#d9d2c4" />
        </linearGradient>
        <radialGradient id="nexus-rim" cx="0.85" cy="0.4" r="0.8">
          <stop offset="0%" stopColor="#ffb07a" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#ffb07a" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="nexus-visor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1c2230" />
          <stop offset="100%" stopColor="#07090d" />
        </linearGradient>
        <radialGradient id="nexus-lantern" cx="0.5" cy="0.45" r="0.6">
          <stop offset="0%" stopColor="#ffe3a3" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#ffe3a3" stopOpacity="0" />
        </radialGradient>
        <filter id="nexus-eye-glow" filterUnits="userSpaceOnUse" x="-10" y="-20" width="130" height="150">
          <feGaussianBlur stdDeviation="1.6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    </svg>
  );
}

type Pose = { body: TargetAndTransition; leftArm: number; rightArm: number; transition: Transition };

const loop = (duration: number): Transition => ({ repeat: Infinity, duration, ease: "easeInOut" });

/** Whole-body motion and arm angles per animation state. */
function pose(mode: RobotMode): Pose {
  switch (mode) {
    case "walking":
      return { body: { y: [0, -3, 0], rotate: [-3, 3, -3] }, leftArm: 20, rightArm: -20, transition: loop(0.5) };
    case "receiving_task":
      return {
        body: { y: [0, -4, 0], scale: [1, 1.05, 1] },
        leftArm: -40,
        rightArm: -60,
        transition: { duration: 0.6 },
      };
    case "thinking":
      return { body: { rotate: [0, -3, 0, 3, 0], y: [0, -1, 0] }, leftArm: 10, rightArm: -100, transition: loop(3) };
    case "using_tool":
      return { body: { x: [0, 1.5, 0] }, leftArm: 10, rightArm: -75, transition: loop(0.6) };
    case "handoff":
      return { body: { rotate: [0, -4, 0] }, leftArm: 5, rightArm: -95, transition: { duration: 0.6 } };
    case "debating":
      return { body: { rotate: [2, 5, 2], x: [0, 2, 0] }, leftArm: -30, rightArm: -60, transition: loop(0.9) };
    case "testing":
      return { body: { y: [0, -1, 0] }, leftArm: -20, rightArm: -20, transition: loop(1.6) };
    case "retrying":
      return {
        body: { x: [-2, 2, -2, 2, 0], rotate: [0, -6, 6, 0] },
        leftArm: 30,
        rightArm: -30,
        transition: loop(0.9),
      };
    case "waiting_approval":
      return { body: { y: 7, scaleY: 0.92 }, leftArm: -70, rightArm: -70, transition: { duration: 0.5 } };
    case "success":
      return {
        body: { y: [0, -14, 0], rotate: [0, -6, 6, 0] },
        leftArm: -150,
        rightArm: -150,
        transition: { duration: 0.7, repeat: 2 },
      };
    case "failed":
      return { body: { y: 3, rotate: 8 }, leftArm: 25, rightArm: 25, transition: { duration: 0.5 } };
    case "sleeping":
      return { body: { y: [0, -0.8, 0], rotate: -4 }, leftArm: 15, rightArm: -15, transition: loop(4) };
    case "waving":
      return { body: { y: [0, -2, 0] }, leftArm: 8, rightArm: -150, transition: loop(1.2) };
    case "alarm":
      return { body: { x: [-2, 2, -2, 2, 0] }, leftArm: -120, rightArm: -120, transition: loop(0.5) };
    default:
      return { body: { y: [0, -1.5, 0] }, leftArm: 8, rightArm: -8, transition: loop(2.6) };
  }
}

interface RobotProps {
  avatar: Avatar;
  state: RobotState;
  isShogun?: boolean;
  label?: string;
  size?: number;
  showBubble?: boolean;
}

export const Robot = memo(function Robot({ avatar, state, isShogun, label, size = 96, showBubble = true }: RobotProps) {
  const p = pose(state.mode);
  const scale = avatar.size === "large" ? 1.25 : avatar.size === "small" ? 0.78 : 1;
  const w = size * scale;
  const regalia = isShogun ? ShogunRegalia() : null;
  const active = state.mode !== "idle" && state.mode !== "sleeping";
  return (
    <div className="relative flex flex-col items-center" style={{ width: w }} data-robot-mode={state.mode}>
      {showBubble && state.bubble && active && (
        <motion.div
          key={state.mode}
          initial={{ opacity: 0, y: 6, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="absolute -top-2 z-10 max-w-[220px] -translate-y-full rounded-xl border border-border bg-[color-mix(in_srgb,var(--lacquer)_92%,transparent)] px-2.5 py-1.5 text-[11px] leading-snug text-text shadow-lg"
        >
          <span className="line-clamp-3">{state.bubble}</span>
          <span className="absolute -bottom-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 border-r border-b border-border bg-[color-mix(in_srgb,var(--lacquer)_92%,transparent)]" />
        </motion.div>
      )}
      <svg viewBox="-6 -14 112 134" width={w} height={w * 1.2} className="overflow-visible">
        <ellipse cx={50} cy={114} rx={24} ry={4.5} fill="black" opacity={0.35} />
        <motion.g animate={p.body} transition={p.transition} style={{ transformOrigin: "50px 100px" }}>
          {regalia?.cape}
          {/* legs */}
          <rect x={37} y={92} width={10} height={17} rx={5} fill="url(#nexus-shell)" />
          <rect x={53} y={92} width={10} height={17} rx={5} fill="url(#nexus-shell)" />
          {/* arms (pivot at shoulders) */}
          <motion.g
            animate={{ rotate: p.leftArm }}
            transition={{ type: "spring", stiffness: 140, damping: 12 }}
            style={{ transformOrigin: "30px 68px" }}
          >
            <rect x={22} y={66} width={9} height={24} rx={4.5} fill="url(#nexus-shell)" />
            <circle cx={26.5} cy={90} r={4.6} fill="#e8e2d6" />
          </motion.g>
          <motion.g
            animate={{ rotate: state.mode === "waving" ? [-150, -110, -150] : p.rightArm }}
            transition={state.mode === "waving" ? loop(0.8) : { type: "spring", stiffness: 140, damping: 12 }}
            style={{ transformOrigin: "70px 68px" }}
          >
            <rect x={69} y={66} width={9} height={24} rx={4.5} fill="url(#nexus-shell)" />
            <circle cx={73.5} cy={90} r={4.6} fill="#e8e2d6" />
            <g transform="translate(-6 18)">
              <Prop kind={avatar.prop} color={avatar.color} />
            </g>
          </motion.g>
          {avatar.prop === "envelope" && <Prop kind="envelope" color={avatar.color} />}
          {/* body */}
          <rect x={29} y={60} width={42} height={38} rx={17} fill="url(#nexus-shell)" />
          <rect x={29} y={60} width={42} height={38} rx={17} fill="url(#nexus-rim)" />
          <motion.circle
            cx={50}
            cy={78}
            r={3.4}
            fill="var(--cyan)"
            animate={{ opacity: active ? [0.5, 1, 0.5] : [0.35, 0.6, 0.35] }}
            transition={loop(active ? 0.9 : 2.8)}
            filter="url(#nexus-eye-glow)"
          />
          {/* head */}
          <g>
            <circle cx={15} cy={37} r={7} fill="url(#nexus-shell)" />
            <circle cx={85} cy={37} r={7} fill="url(#nexus-shell)" />
            <circle cx={15} cy={37} r={3.6} fill="none" stroke="var(--cyan)" strokeWidth={1.6} opacity={0.9} />
            <circle cx={85} cy={37} r={3.6} fill="none" stroke="var(--cyan)" strokeWidth={1.6} opacity={0.9} />
            <rect x={15} y={8} width={70} height={58} rx={27} fill="url(#nexus-shell)" />
            <rect x={15} y={8} width={70} height={58} rx={27} fill="url(#nexus-rim)" />
            <ellipse cx={34} cy={17} rx={11} ry={4.5} fill="white" opacity={0.7} transform="rotate(-18 34 17)" />
            {/* headband with flowing tails */}
            <path d="M17,25 C30,17 70,17 83,25 L83,31 C70,23 30,23 17,31 Z" fill={avatar.headband} />
            <motion.path
              d="M82,27 C90,27 95,31 99,37 M82,29 C89,31 92,37 94,43"
              stroke={avatar.headband}
              strokeWidth={3}
              strokeLinecap="round"
              fill="none"
              animate={{ rotate: [0, 6, 0] }}
              transition={loop(1.8)}
              style={{ transformOrigin: "82px 28px" }}
            />
            <rect x={24} y={22} width={52} height={33} rx={15} fill="url(#nexus-visor)" />
            <path d="M28,27 Q50,22 72,27" stroke="white" strokeOpacity={0.12} strokeWidth={2} fill="none" />
            <Eyes expression={state.expression} />
            {regalia?.crest}
          </g>
          {state.mode === "retrying" && (
            <motion.g
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
              style={{ transformOrigin: "50px -4px" }}
            >
              <circle cx={40} cy={-4} r={2.4} fill="var(--warning)" />
              <circle cx={60} cy={-4} r={2} fill="var(--cyan)" />
              <circle cx={50} cy={-11} r={1.6} fill="var(--warning)" />
            </motion.g>
          )}
          {state.mode === "sleeping" && (
            <motion.text
              x={80}
              y={4}
              fontSize={12}
              fill="var(--text-muted)"
              animate={{ y: [4, -8], opacity: [1, 0] }}
              transition={loop(2.2)}
            >
              z
            </motion.text>
          )}
          {state.mode === "failed" && (
            <motion.circle
              cx={58}
              cy={0}
              r={6}
              fill="#777"
              animate={{ y: [0, -14], opacity: [0.6, 0], scale: [0.6, 1.6] }}
              transition={loop(1.6)}
            />
          )}
        </motion.g>
      </svg>
      {state.mode === "retrying" && state.attempt > 0 && (
        <span className="absolute top-4 right-0 rounded-full bg-warning px-1.5 text-[10px] font-bold text-[var(--ink)]">
          ×{state.attempt}
        </span>
      )}
      {label && (
        <span className="mt-0.5 rounded-full bg-black/40 px-2 text-[11px] whitespace-nowrap font-medium text-text/90 backdrop-blur-sm">
          {label}
        </span>
      )}
    </div>
  );
});
