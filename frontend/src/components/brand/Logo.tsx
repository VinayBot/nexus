"use client";

import { motion } from "motion/react";

/** NEXUS mark: a hex core with an orbiting ring and a pulsing nucleus. */
export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg viewBox="-24 -24 48 48" width={size} height={size} aria-hidden className="shrink-0 overflow-visible">
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffd89a" />
          <stop offset="0.5" stopColor="#ff6b3d" />
          <stop offset="1" stopColor="#ff4f6d" />
        </linearGradient>
      </defs>
      <path
        d="M0,-19 L16.5,-9.5 L16.5,9.5 L0,19 L-16.5,9.5 L-16.5,-9.5 Z"
        fill="url(#logo-grad)"
        style={{ filter: "drop-shadow(0 0 8px rgb(255 120 60 / 0.7))" }}
      />
      <path d="M0,-12 L10.4,-6 L10.4,6 L0,12 L-10.4,6 L-10.4,-6 Z" fill="#0b0d16" />
      <path
        d="M-5,6 V-6 L5,6 V-6"
        stroke="#ffd89a"
        strokeWidth={2.2}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <motion.g animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 9, ease: "linear" }}>
        <ellipse
          rx={23}
          ry={8}
          fill="none"
          stroke="#4fe3f0"
          strokeOpacity={0.55}
          strokeWidth={1}
          transform="rotate(-25)"
        />
        <circle cx={21} cy={-9} r={2} fill="#4fe3f0" style={{ filter: "drop-shadow(0 0 4px #4fe3f0)" }} />
      </motion.g>
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-[0.28em] ${className}`}>
      <span className="title-gradient">NEXUS</span>
    </span>
  );
}
