"use client";

import { motion } from "motion/react";

/**
 * Hand-held gear, drawn in the right hand's local space (hand centre at 0,0).
 * Every prop glows in the robot's accent colour.
 */
export function Prop({ kind, accent, active }: { kind: string; accent: string; active: boolean }) {
  const glow = { filter: "url(#nexus-led-glow)" };
  switch (kind) {
    case "staff": // command staff with a pulsing energy core
      return (
        <g transform="translate(0 -4) rotate(-12)">
          <rect x={-1.4} y={-30} width={2.8} height={40} rx={1.4} fill="#3a404d" />
          <motion.circle
            cx={0}
            cy={-33}
            r={4.5}
            fill={accent}
            {...glow}
            animate={{ r: active ? [4.5, 6, 4.5] : 4.5 }}
            transition={{ repeat: Infinity, duration: 1.2 }}
          />
          <path d="M-5,-29 L0,-40 L5,-29" stroke={accent} strokeWidth={1.2} fill="none" />
        </g>
      );
    case "tablet": // holographic planning tablet
      return (
        <g transform="translate(4 -8) rotate(-10)">
          <rect
            x={-1}
            y={-10}
            width={16}
            height={12}
            rx={1.5}
            fill={accent}
            opacity={0.18}
            stroke={accent}
            strokeWidth={0.8}
          />
          {[0, 1, 2].map((i) => (
            <motion.rect
              key={i}
              x={1.5}
              y={-7.5 + i * 3.4}
              width={active ? 11 : 7 + i * 2}
              height={1.2}
              rx={0.6}
              fill={accent}
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.6, delay: i * 0.2 }}
            />
          ))}
        </g>
      );
    case "scanner": // handheld scanner throwing a beam
      return (
        <g transform="translate(2 -2)">
          <rect x={-2} y={-4} width={9} height={6} rx={1.5} fill="#3a404d" />
          <circle cx={7} cy={-1} r={1.6} fill={accent} {...glow} />
          {active && (
            <motion.path
              d="M8,-1 L30,-10 L30,8 Z"
              fill={accent}
              animate={{ opacity: [0.08, 0.28, 0.08] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
          )}
        </g>
      );
    case "stylus":
      return (
        <g transform="translate(0 -2) rotate(30)">
          <rect x={-1} y={-14} width={2} height={16} rx={1} fill="#c7cbd6" />
          <circle cx={0} cy={2.5} r={1.4} fill={accent} {...glow} />
        </g>
      );
    case "wrench":
      return (
        <g transform="translate(0 -4) rotate(-30)">
          <rect x={-1.5} y={-14} width={3} height={16} rx={1.2} fill="#9aa3ad" />
          <path d="M-5,-16 A5,5 0 1,1 5,-16 L2,-16 L2,-13 L-2,-13 L-2,-16 Z" fill="#c4cbd4" />
          <circle cx={0} cy={2} r={1.4} fill={accent} {...glow} />
        </g>
      );
    case "shield": // hex energy shield
      return (
        <motion.g
          transform="translate(6 -6)"
          animate={{ opacity: active ? [0.7, 1, 0.7] : 0.85 }}
          transition={{ repeat: Infinity, duration: 1.4 }}
        >
          <path
            d="M0,-14 L12,-7 L12,7 L0,14 L-12,7 L-12,-7 Z"
            fill={accent}
            fillOpacity={0.18}
            stroke={accent}
            strokeWidth={1.4}
            {...glow}
          />
          <path
            d="M0,-7 L6,-3.5 L6,3.5 L0,7 L-6,3.5 L-6,-3.5 Z"
            fill="none"
            stroke={accent}
            strokeWidth={0.8}
            opacity={0.7}
          />
        </motion.g>
      );
    case "blade": // energy blade
      return (
        <g transform="translate(0 -2) rotate(-40)">
          <rect x={-1.6} y={-2} width={3.2} height={7} rx={1} fill="#3a404d" />
          <motion.rect
            x={-1.3}
            y={-30}
            width={2.6}
            height={28}
            rx={1.3}
            fill={accent}
            {...glow}
            animate={{ opacity: active ? [0.7, 1, 0.7] : 0.9 }}
            transition={{ repeat: Infinity, duration: 0.5 }}
          />
          <rect x={-0.5} y={-29} width={1} height={26} rx={0.5} fill="white" opacity={0.7} />
        </g>
      );
    case "scale": // hologram balance
      return (
        <g transform="translate(2 -14)" stroke={accent} strokeWidth={1} fill="none" opacity={0.9}>
          <path d="M0,-8 V6 M-11,-6 H11" />
          <path d="M-11,-6 l-4,8 h8 Z M11,-6 l-4,8 h8 Z" fill={accent} fillOpacity={0.25} />
        </g>
      );
    case "beacon":
      return (
        <g transform="translate(0 -6)">
          <rect x={-3} y={-4} width={6} height={9} rx={2} fill="#3a404d" />
          <motion.circle
            cx={0}
            cy={-6}
            r={3}
            fill={accent}
            {...glow}
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ repeat: Infinity, duration: 1 }}
          />
        </g>
      );
    default:
      return null;
  }
}

/** Gear mounted on the body rather than held: jet wings, guide halo. */
export function BodyGear({ kind, accent, active }: { kind: string; accent: string; active: boolean }) {
  if (kind === "jets") {
    return (
      <g>
        <path d="M32,64 L14,56 L19,76 Z M68,64 L86,56 L81,76 Z" fill={accent} opacity={0.85} />
        <motion.path
          d="M15,76 l2.5,10 l2.5,-10 Z M80,76 l2.5,10 l2.5,-10 Z"
          fill="#ffd08a"
          animate={{ scaleY: active ? [1, 1.8, 1] : [1, 1.3, 1] }}
          transition={{ repeat: Infinity, duration: 0.25 }}
          style={{ transformOrigin: "50px 76px" }}
        />
      </g>
    );
  }
  if (kind === "halo") {
    return (
      <motion.ellipse
        cx={50}
        cy={-3}
        rx={18}
        ry={4}
        fill="none"
        stroke={accent}
        strokeWidth={2}
        filter="url(#nexus-led-glow)"
        animate={{ ry: [4, 5, 4], opacity: [0.7, 1, 0.7] }}
        transition={{ repeat: Infinity, duration: 2 }}
      />
    );
  }
  return null;
}

/** The Commander's light-fin crest. */
export function CommanderCrest({ accent }: { accent: string }) {
  return (
    <g filter="url(#nexus-led-glow)">
      <path d="M50,8 L45,-12 L50,-7 L55,-12 Z" fill={accent} />
      <path d="M43,10 L30,-4 L40,4 Z M57,10 L70,-4 L60,4 Z" fill={accent} opacity={0.85} />
    </g>
  );
}
