"use client";

import { motion } from "motion/react";
import type { RobotMode } from "@/lib/robotMachine";

const loop = (duration: number, delay = 0) => ({ repeat: Infinity, duration, delay, ease: "easeOut" as const });

/** Sparks flying out from a point (tool use, failure). */
function Sparks({ x, y, color, count = 6 }: { x: number; y: number; color: string; count?: number }) {
  return (
    <g>
      {Array.from({ length: count }, (_, i) => {
        const a = (i / count) * Math.PI * 2 + 0.4;
        return (
          <motion.circle
            key={i}
            cx={x}
            cy={y}
            r={1}
            fill={color}
            animate={{ cx: [x, x + Math.cos(a) * 14], cy: [y, y + Math.sin(a) * 14 + 4], opacity: [1, 0] }}
            transition={loop(0.55, i * 0.07)}
          />
        );
      })}
    </g>
  );
}

/** Mode-specific overlays drawn in robot space, on top of the body. */
export function ModeEffects({ mode, accent }: { mode: RobotMode; accent: string }) {
  switch (mode) {
    case "thinking": // holo rings expanding around the head
      return (
        <g>
          {[0, 1, 2].map((i) => (
            <motion.ellipse
              key={i}
              cx={50}
              cy={28}
              fill="none"
              stroke={accent}
              strokeWidth={1}
              initial={{ rx: 30, ry: 8, opacity: 0 }}
              animate={{ rx: [30, 48], ry: [8, 13], opacity: [0.8, 0] }}
              transition={loop(1.8, i * 0.6)}
            />
          ))}
        </g>
      );
    case "using_tool":
      return <Sparks x={74} y={92} color="#ffd08a" />;
    case "receiving_task": // download beam from above
      return (
        <motion.path
          d="M38,-24 L62,-24 L72,60 L28,60 Z"
          fill={accent}
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.22, 0] }}
          transition={{ duration: 0.9 }}
        />
      );
    case "testing": // scan bar sweeping the body
      return (
        <motion.rect
          x={20}
          width={60}
          height={2}
          rx={1}
          fill={accent}
          filter="url(#nexus-led-glow)"
          animate={{ y: [6, 104, 6], opacity: [0.9, 0.6, 0.9] }}
          transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}
        />
      );
    case "debating": // sound-wave arcs
      return (
        <g stroke={accent} strokeWidth={1.4} fill="none" strokeLinecap="round">
          {[0, 1, 2].map((i) => (
            <motion.path
              key={i}
              d={`M${86 + i * 5},20 Q${91 + i * 5},30 ${86 + i * 5},40`}
              animate={{ opacity: [0, 1, 0] }}
              transition={loop(0.9, i * 0.15)}
            />
          ))}
        </g>
      );
    case "waiting_approval": // hologram card over the head
      return (
        <motion.g animate={{ y: [0, -3, 0] }} transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}>
          <path d="M50,0 L36,-12 L64,-12 Z" fill={accent} opacity={0.15} />
          <rect
            x={34}
            y={-30}
            width={32}
            height={18}
            rx={3}
            fill={accent}
            fillOpacity={0.15}
            stroke={accent}
            strokeWidth={1}
          />
          <motion.path
            d="M43,-21 l4,4 l8,-8"
            stroke={accent}
            strokeWidth={2}
            fill="none"
            strokeLinecap="round"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ repeat: Infinity, duration: 1.4 }}
          />
        </motion.g>
      );
    case "success": // light burst
      return (
        <g>
          {Array.from({ length: 10 }, (_, i) => {
            const a = (i / 10) * Math.PI * 2;
            return (
              <motion.line
                key={i}
                x1={50 + Math.cos(a) * 30}
                y1={55 + Math.sin(a) * 40}
                x2={50 + Math.cos(a) * 44}
                y2={55 + Math.sin(a) * 56}
                stroke={i % 2 ? accent : "#ffd08a"}
                strokeWidth={2}
                strokeLinecap="round"
                animate={{ opacity: [0, 1, 0], pathLength: [0, 1] }}
                transition={loop(0.9, i * 0.03)}
              />
            );
          })}
        </g>
      );
    case "failed":
      return (
        <g>
          <Sparks x={64} y={66} color="#ff7a45" count={5} />
          <motion.circle
            cx={58}
            cy={0}
            r={6}
            fill="#777"
            animate={{ y: [0, -16], opacity: [0.6, 0], scale: [0.6, 1.8] }}
            transition={loop(1.6)}
          />
        </g>
      );
    case "retrying": // orbiting retry electrons
      return (
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.1, ease: "linear" }}
          style={{ transformOrigin: "50px 28px" }}
        >
          <circle cx={14} cy={28} r={2.2} fill="var(--warning)" />
          <circle cx={86} cy={28} r={1.8} fill={accent} />
        </motion.g>
      );
    case "sleeping":
      return (
        <g fill="var(--text-muted)" fontWeight={700}>
          {[0, 1].map((i) => (
            <motion.text
              key={i}
              x={80 + i * 6}
              y={4}
              fontSize={10 - i * 2}
              animate={{ y: [4, -12], opacity: [0, 1, 0] }}
              transition={loop(2.4, i * 1.2)}
            >
              z
            </motion.text>
          ))}
        </g>
      );
    case "alarm": // rotating siren beam
      return (
        <motion.path
          d="M66,-10 L100,-22 L100,2 Z"
          fill="#ff4d4f"
          opacity={0.35}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
          style={{ transformOrigin: "66px -10px" }}
        />
      );
    default:
      return null;
  }
}
