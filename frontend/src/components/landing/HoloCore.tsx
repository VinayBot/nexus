"use client";

import { motion } from "motion/react";

const TICKS = Array.from({ length: 72 }, (_, i) => i);

/** A slowly rotating holographic reactor ring behind the hero title. */
export function HoloCore({ className }: { className?: string }) {
  return (
    <svg viewBox="-300 -300 600 600" className={className} aria-hidden>
      <defs>
        <radialGradient id="core-glow">
          <stop offset="0" stopColor="var(--ember)" stopOpacity="0.35" />
          <stop offset="0.45" stopColor="var(--coral)" stopOpacity="0.12" />
          <stop offset="1" stopColor="#05060b" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle r={290} fill="url(#core-glow)" />
      <motion.g animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 120, ease: "linear" }}>
        <circle r={262} fill="none" stroke="rgb(79 227 240 / 0.28)" strokeWidth={1} strokeDasharray="2 10" />
        {TICKS.map((i) => (
          <line
            key={i}
            x1={0}
            y1={-246}
            x2={0}
            y2={i % 6 === 0 ? -232 : -240}
            stroke={i % 6 === 0 ? "rgb(79 227 240 / 0.7)" : "rgb(79 227 240 / 0.25)"}
            strokeWidth={i % 6 === 0 ? 2 : 1}
            transform={`rotate(${i * 5})`}
          />
        ))}
      </motion.g>
      <motion.g animate={{ rotate: -360 }} transition={{ repeat: Infinity, duration: 60, ease: "linear" }}>
        <circle
          r={210}
          fill="none"
          stroke="rgb(var(--gold-rgb) / 0.35)"
          strokeWidth={1.5}
          strokeDasharray="140 40 20 40"
        />
        <circle
          cx={0}
          cy={-210}
          r={4}
          fill="var(--sun-gold)"
          style={{ filter: "drop-shadow(0 0 6px var(--sun-gold))" }}
        />
      </motion.g>
      <motion.g animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 36, ease: "linear" }}>
        <circle r={170} fill="none" stroke="rgb(139 123 255 / 0.3)" strokeWidth={1} strokeDasharray="4 6" />
        <circle cx={170} cy={0} r={3} fill="#8b7bff" style={{ filter: "drop-shadow(0 0 6px #8b7bff)" }} />
      </motion.g>
      <motion.circle
        r={130}
        fill="none"
        stroke="rgb(var(--ember-rgb) / 0.25)"
        strokeWidth={1}
        animate={{ r: [126, 136, 126], opacity: [0.5, 1, 0.5] }}
        transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
      />
    </svg>
  );
}
