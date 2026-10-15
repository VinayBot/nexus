"use client";

import { motion } from "motion/react";

const LEVEL_COLOR: Record<string, string> = {
  LOW: "var(--success)",
  MEDIUM: "var(--warning)",
  HIGH: "var(--ember)",
  CRITICAL: "var(--error)",
};

/** Semicircular risk gauge whose needle swings to the score (0–1). */
export function RiskMeter({ score, level }: { score: number; level: string }) {
  const angle = -90 + Math.min(1, Math.max(0, score)) * 180;
  const color = LEVEL_COLOR[level] ?? "var(--text-muted)";
  return (
    <div className="flex flex-col items-center" aria-label={`Risk ${level}, score ${score.toFixed(2)}`}>
      <svg viewBox="0 0 120 70" className="w-36">
        <defs>
          <linearGradient id="riskarc" x1="0" x2="1">
            <stop offset="0" stopColor="#3fd18b" />
            <stop offset="0.35" stopColor="#ffb020" />
            <stop offset="0.65" stopColor="#f2662a" />
            <stop offset="1" stopColor="#ff4d4f" />
          </linearGradient>
        </defs>
        <path
          d="M10,62 A50,50 0 0 1 110,62"
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={10}
          strokeLinecap="round"
        />
        <path
          d="M10,62 A50,50 0 0 1 110,62"
          fill="none"
          stroke="url(#riskarc)"
          strokeWidth={10}
          strokeLinecap="round"
          opacity={0.85}
        />
        <motion.g
          initial={{ rotate: -90 }}
          animate={{ rotate: angle }}
          transition={{ type: "spring", stiffness: 60, damping: 9 }}
          style={{ transformOrigin: "60px 62px" }}
        >
          <path d="M60,62 L60,18" stroke={color} strokeWidth={3} strokeLinecap="round" />
        </motion.g>
        <circle cx={60} cy={62} r={5} fill={color} />
      </svg>
      <span className="-mt-1 font-display text-sm font-bold" style={{ color }}>
        {level} · {score.toFixed(2)}
      </span>
    </div>
  );
}
