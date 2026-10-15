"use client";

import { motion, type TargetAndTransition, type Transition } from "motion/react";
import { memo, useId } from "react";
import type { RobotMode, RobotState } from "@/lib/robotMachine";
import { darken, isDark, lighten } from "./color";
import { ModeEffects } from "./Effects";
import { Eyes } from "./Eyes";
import { BodyGear, CommanderCrest, Prop } from "./Props";

export interface Avatar {
  /** Armour shell colour. */
  color: string;
  /** LED / trim colour (eyes, core, stripes, props). */
  accent: string;
  prop: string;
  size?: "small" | "normal" | "large";
}

/** Shared SVG defs (glow filters, visor); render once per page. */
export function RobotDefs() {
  return (
    <svg width={0} height={0} className="absolute" aria-hidden>
      <defs>
        <linearGradient id="nexus-visor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a2130" />
          <stop offset="100%" stopColor="#05070b" />
        </linearGradient>
        <filter id="nexus-led-glow" filterUnits="userSpaceOnUse" x="-60" y="-80" width="240" height="260">
          <feGaussianBlur stdDeviation="1.8" result="b" />
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
      return {
        body: { x: [0, 3, 0, -3, 0], rotate: [0, 6, 0, -6, 0] },
        leftArm: 25,
        rightArm: -25,
        transition: loop(0.9),
      };
    case "receiving_task":
      return {
        body: { y: [0, -6, 0], scale: [1, 1.06, 1] },
        leftArm: -40,
        rightArm: -60,
        transition: { duration: 0.6 },
      };
    case "thinking":
      return { body: { rotate: [0, -3, 0, 3, 0] }, leftArm: 10, rightArm: -100, transition: loop(3) };
    case "using_tool":
      return { body: { x: [0, 1.5, 0] }, leftArm: 10, rightArm: -75, transition: loop(0.4) };
    case "handoff":
      return { body: { rotate: [0, -5, 0] }, leftArm: 5, rightArm: -95, transition: { duration: 0.6 } };
    case "debating":
      return { body: { rotate: [2, 6, 2], x: [0, 2, 0] }, leftArm: -30, rightArm: -60, transition: loop(0.8) };
    case "testing":
      return { body: { y: [0, -1, 0] }, leftArm: -20, rightArm: -20, transition: loop(1.6) };
    case "retrying":
      return {
        body: { x: [-2.5, 2.5, -1.5, 2, 0], skewX: [0, 6, -6, 0] },
        leftArm: 30,
        rightArm: -30,
        transition: loop(0.5),
      };
    case "waiting_approval":
      return { body: { y: 4 }, leftArm: -60, rightArm: -60, transition: { duration: 0.5 } };
    case "success": // barrel spin + boost
      return {
        body: { y: [0, -18, 0], scaleX: [1, -1, 1] },
        leftArm: -150,
        rightArm: -150,
        transition: { duration: 0.8, repeat: 2 },
      };
    case "failed":
      return { body: { y: 6, rotate: 10 }, leftArm: 30, rightArm: 25, transition: { duration: 0.6 } };
    case "sleeping":
      return { body: { y: 8, rotate: -4 }, leftArm: 18, rightArm: -18, transition: { duration: 1.2 } };
    case "waving":
      return { body: { rotate: [0, -2, 0] }, leftArm: 8, rightArm: -150, transition: loop(1.2) };
    case "alarm":
      return { body: { x: [-2, 2, -2, 2, 0] }, leftArm: -120, rightArm: -120, transition: loop(0.4) };
    default:
      return { body: { rotate: [0, -1.2, 0, 1.2, 0] }, leftArm: 8, rightArm: -8, transition: loop(5) };
  }
}

const GLITCH = "drop-shadow(2px 0 0 rgb(255 0 90 / 0.7)) drop-shadow(-2px 0 0 rgb(0 240 255 / 0.7))";

/** An arm: armoured upper segment, forearm, glowing claw hand. `side` mirrors it. */
function Arm({ x, shell, dark, accent }: { x: number; shell: string; dark: string; accent: string }) {
  return (
    <g>
      <path d={`M${x - 4.5},66 L${x + 4.5},66 L${x + 3.5},80 L${x - 3.5},80 Z`} fill={shell} />
      <rect x={x - 3.5} y={80} width={7} height={11} rx={2} fill={dark} />
      <rect x={x - 3.5} y={84} width={7} height={1.4} fill={accent} opacity={0.9} />
      <path
        d={`M${x - 4},91 l-1,5 l3,-2 M${x + 4},91 l1,5 l-3,-2`}
        stroke={dark}
        strokeWidth={2}
        strokeLinecap="round"
        fill="none"
      />
      <circle cx={x} cy={92} r={2.4} fill={accent} filter="url(#nexus-led-glow)" />
    </g>
  );
}

interface RobotProps {
  avatar: Avatar;
  state: RobotState;
  isCommander?: boolean;
  label?: string;
  size?: number;
  showBubble?: boolean;
}

export const Robot = memo(function Robot({
  avatar,
  state,
  isCommander,
  label,
  size = 96,
  showBubble = true,
}: RobotProps) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const { mode } = state;
  const p = pose(mode);
  const scale = avatar.size === "large" ? 1.25 : avatar.size === "small" ? 0.78 : 1;
  const w = size * scale;
  const active = mode !== "idle" && mode !== "sleeping";
  const powered = mode !== "sleeping" && mode !== "failed";
  const accent = mode === "alarm" ? "#ff4d4f" : (avatar.accent ?? "#4fe3f0");
  const shellBase = avatar.color;
  const dark = isDark(shellBase) ? lighten(shellBase, 0.12) : darken(shellBase, 0.45);
  const shell = `url(#shell-${uid})`;
  const hasAntenna = !isCommander && avatar.prop !== "halo";
  const boost = mode === "success" || mode === "receiving_task" || mode === "walking";

  return (
    <div className="relative flex flex-col items-center" style={{ width: w }} data-robot-mode={mode}>
      {showBubble && state.bubble && active && (
        <motion.div
          key={mode}
          initial={{ opacity: 0, y: 6, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="pointer-events-none absolute -top-1 z-20 w-max max-w-[170px] -translate-y-full rounded-md border bg-[rgb(8_11_20/0.94)] px-2 py-1 font-mono text-[10px] leading-snug text-text shadow-lg"
          style={{
            borderColor: `color-mix(in srgb, ${accent} 55%, transparent)`,
            boxShadow: `0 0 14px -4px ${accent}`,
          }}
        >
          <span className="line-clamp-2">{state.bubble}</span>
        </motion.div>
      )}
      <motion.svg
        viewBox="-10 -26 120 150"
        width={w}
        height={w * 1.25}
        className="overflow-visible"
        style={{
          filter: mode === "retrying" ? GLITCH : mode === "sleeping" ? "saturate(0.4) brightness(0.75)" : undefined,
        }}
        animate={mode === "failed" ? { opacity: [1, 0.55, 1, 0.8, 1] } : { opacity: 1 }}
        transition={mode === "failed" ? { repeat: Infinity, duration: 1.3 } : { duration: 0.3 }}
      >
        <defs>
          <linearGradient id={`shell-${uid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={lighten(shellBase, 0.45)} />
            <stop offset="45%" stopColor={shellBase} />
            <stop offset="100%" stopColor={darken(shellBase, 0.35)} />
          </linearGradient>
        </defs>

        {/* holo landing ring */}
        <motion.ellipse
          cx={50}
          cy={118}
          rx={22}
          ry={4}
          fill="none"
          stroke={accent}
          strokeWidth={1.2}
          animate={powered ? { rx: [20, 26, 20], opacity: [0.7, 0.25, 0.7] } : { rx: 22, opacity: 0.15 }}
          transition={loop(2.4)}
        />
        <ellipse cx={50} cy={118} rx={16} ry={2.6} fill="black" opacity={0.35} />

        {/* hover bob, separate from the pose so both compose */}
        <motion.g animate={powered ? { y: [0, -3.5, 0] } : { y: 0 }} transition={loop(2.6)}>
          <motion.g animate={p.body} transition={p.transition} style={{ transformOrigin: "50px 70px" }}>
            {/* thruster pods + flames */}
            <path d="M38,96 L47,96 L45,106 L40,106 Z M53,96 L62,96 L60,106 L55,106 Z" fill={dark} />
            {powered && (
              <motion.path
                d="M40.5,106 L42.5,116 L44.5,106 Z M55.5,106 L57.5,116 L59.5,106 Z"
                fill={boost ? "#ffd08a" : accent}
                filter="url(#nexus-led-glow)"
                animate={{ scaleY: boost ? [1, 1.9, 1.3, 1.9] : [0.7, 1, 0.8, 1], opacity: [0.9, 0.6, 1, 0.7] }}
                transition={{ repeat: Infinity, duration: 0.22 }}
                style={{ transformOrigin: "50px 106px" }}
              />
            )}

            <BodyGear kind={avatar.prop} accent={accent} active={active} />

            {/* arms pivot at the shoulders */}
            <motion.g
              animate={{ rotate: p.leftArm }}
              transition={{ type: "spring", stiffness: 140, damping: 12 }}
              style={{ transformOrigin: "27px 66px" }}
            >
              <Arm x={27} shell={shell} dark={dark} accent={accent} />
            </motion.g>
            <motion.g
              animate={{ rotate: mode === "waving" ? [-150, -110, -150] : p.rightArm }}
              transition={mode === "waving" ? loop(0.8) : { type: "spring", stiffness: 140, damping: 12 }}
              style={{ transformOrigin: "73px 66px" }}
            >
              <Arm x={73} shell={shell} dark={dark} accent={accent} />
              <g transform="translate(73 93)">
                <Prop kind={avatar.prop} accent={accent} active={active} />
              </g>
            </motion.g>

            {/* torso */}
            <path d="M31,60 L69,60 L74,72 L66,98 L34,98 L26,72 Z" fill={shell} />
            <path d="M38,66 L62,66 L65,74 L60,92 L40,92 L35,74 Z" fill={dark} opacity={0.85} />
            <path d="M31,60 L69,60 L67,63 L33,63 Z" fill={accent} opacity={0.75} />
            <path d="M36,94 L64,94" stroke={accent} strokeWidth={1.2} opacity={0.6} />
            {/* reactor core */}
            <motion.circle
              cx={50}
              cy={78}
              r={4.6}
              fill={accent}
              filter="url(#nexus-led-glow)"
              animate={{ opacity: powered ? (active ? [0.6, 1, 0.6] : [0.45, 0.8, 0.45]) : 0.2 }}
              transition={loop(active ? 0.7 : 2.6)}
            />
            <motion.circle
              cx={50}
              cy={78}
              r={8}
              fill="none"
              stroke={accent}
              strokeWidth={1}
              strokeDasharray="3 2.5"
              animate={{ rotate: powered ? 360 : 0 }}
              transition={{ repeat: Infinity, duration: active ? 1.6 : 6, ease: "linear" }}
              style={{ transformOrigin: "50px 78px" }}
            />

            {/* shoulder pads */}
            <path
              d="M18,62 L32,58 L34,68 L20,70 Z"
              fill={shell}
              stroke={accent}
              strokeWidth={0.8}
              strokeOpacity={0.7}
            />
            <path
              d="M82,62 L68,58 L66,68 L80,70 Z"
              fill={shell}
              stroke={accent}
              strokeWidth={0.8}
              strokeOpacity={0.7}
            />

            {/* neck */}
            <rect x={44} y={52} width={12} height={9} rx={2} fill={dark} />

            {/* head */}
            <g>
              {hasAntenna && (
                <g>
                  <path d="M64,8 L69,-8" stroke={dark} strokeWidth={2} strokeLinecap="round" />
                  <motion.circle
                    cx={69.5}
                    cy={-9.5}
                    r={2.6}
                    fill={accent}
                    filter="url(#nexus-led-glow)"
                    animate={{ opacity: powered ? [1, 0.2, 1] : 0.15 }}
                    transition={{ repeat: Infinity, duration: mode === "alarm" ? 0.3 : 1.6 }}
                  />
                </g>
              )}
              {/* ear modules */}
              <rect x={14} y={22} width={9} height={18} rx={3} fill={dark} />
              <rect x={77} y={22} width={9} height={18} rx={3} fill={dark} />
              <motion.rect
                x={16.5}
                y={26}
                width={4}
                height={10}
                rx={2}
                fill={accent}
                animate={{ opacity: powered ? [0.4, 1, 0.4] : 0.15 }}
                transition={loop(1.8)}
              />
              <motion.rect
                x={79.5}
                y={26}
                width={4}
                height={10}
                rx={2}
                fill={accent}
                animate={{ opacity: powered ? [1, 0.4, 1] : 0.15 }}
                transition={loop(1.8)}
              />
              {/* helmet */}
              <path d="M22,20 Q22,6 36,5 L64,5 Q78,6 78,20 L80,40 Q80,51 69,52 L31,52 Q20,51 20,40 Z" fill={shell} />
              <path
                d="M30,8 Q36,6 46,6"
                stroke="white"
                strokeOpacity={0.55}
                strokeWidth={2.2}
                strokeLinecap="round"
                fill="none"
              />
              <path
                d="M30,47 L42,47 M58,47 L70,47"
                stroke={accent}
                strokeWidth={1.4}
                strokeLinecap="round"
                opacity={0.8}
              />
              {/* visor */}
              <rect
                x={25}
                y={20}
                width={50}
                height={18}
                rx={9}
                fill="url(#nexus-visor)"
                stroke={accent}
                strokeOpacity={0.35}
                strokeWidth={0.8}
              />
              <clipPath id={`visor-${uid}`}>
                <rect x={25} y={20} width={50} height={18} rx={9} />
              </clipPath>
              <g clipPath={`url(#visor-${uid})`}>
                {powered && (
                  <motion.rect
                    y={20}
                    width={6}
                    height={18}
                    fill={accent}
                    opacity={0.16}
                    animate={{ x: [20, 76] }}
                    transition={{
                      repeat: Infinity,
                      duration: active ? 1.1 : 3.2,
                      ease: "linear",
                      repeatDelay: active ? 0 : 1.5,
                    }}
                  />
                )}
                <Eyes expression={state.expression} color={accent} />
              </g>
              {isCommander && <CommanderCrest accent={accent} />}
            </g>

            <ModeEffects mode={mode} accent={accent} />
          </motion.g>
        </motion.g>
      </motion.svg>
      {mode === "retrying" && state.attempt > 0 && (
        <span className="absolute top-4 right-0 rounded-full bg-warning px-1.5 text-[10px] font-bold text-[var(--ink)]">
          ×{state.attempt}
        </span>
      )}
      {label && (
        <span className="mt-0.5 flex items-center gap-1 rounded-full bg-black/45 px-2 font-display text-[10px] font-semibold tracking-wider whitespace-nowrap text-text/90 uppercase backdrop-blur-sm">
          <span className="size-1.5 rounded-full" style={{ background: accent, boxShadow: `0 0 6px ${accent}` }} />
          {label}
        </span>
      )}
    </div>
  );
});
