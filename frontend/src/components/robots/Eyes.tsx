"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import type { Expression } from "@/lib/robotMachine";

const CYAN = "var(--cyan)";

/** Random blinking, only while the robot has its neutral expression. */
function useBlink(enabled: boolean): boolean {
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let t: ReturnType<typeof setTimeout>;
    const loop = () => {
      t = setTimeout(
        () => {
          setClosed(true);
          t = setTimeout(() => {
            setClosed(false);
            loop();
          }, 140);
        },
        2200 + Math.random() * 4200,
      );
    };
    loop();
    return () => clearTimeout(t);
  }, [enabled]);
  return closed;
}

function Eye({ cx, cy, expression, closed }: { cx: number; cy: number; expression: Expression; closed: boolean }) {
  const stroke = { stroke: CYAN, strokeWidth: 2.6, strokeLinecap: "round" as const, fill: "none" };
  switch (expression) {
    case "happy":
      return <path d={`M${cx - 5},${cy + 2} Q${cx},${cy - 6} ${cx + 5},${cy + 2}`} {...stroke} />;
    case "focused":
      return <path d={`M${cx - 5},${cy} L${cx + 5},${cy}`} {...stroke} strokeWidth={3} />;
    case "sleepy":
      return <path d={`M${cx - 5},${cy - 1} Q${cx},${cy + 5} ${cx + 5},${cy - 1}`} {...stroke} />;
    case "error":
      return cx < 50 ? (
        <path d={`M${cx - 4},${cy - 4} L${cx + 3},${cy} L${cx - 4},${cy + 4}`} {...stroke} />
      ) : (
        <path d={`M${cx + 4},${cy - 4} L${cx - 3},${cy} L${cx + 4},${cy + 4}`} {...stroke} />
      );
    case "confused":
      return (
        <motion.path
          d={`M${cx},${cy} m-1,0 a1,1 0 1,1 2,0 a2.5,2.5 0 1,1 -5,0 a4,4 0 1,1 8,0`}
          {...stroke}
          strokeWidth={2}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        />
      );
    case "thinking":
      return (
        <g>
          <circle cx={cx} cy={cy} r={5} fill="none" stroke={CYAN} strokeOpacity={0.35} strokeWidth={2} />
          <motion.circle
            cx={cx}
            cy={cy}
            r={5}
            fill="none"
            stroke={CYAN}
            strokeWidth={2.4}
            strokeDasharray="8 24"
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.1, ease: "linear" }}
            style={{ transformOrigin: `${cx}px ${cy}px` }}
          />
        </g>
      );
    default:
      return (
        <motion.g
          animate={{ scaleY: closed ? 0.12 : 1 }}
          transition={{ duration: 0.07 }}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        >
          <circle cx={cx} cy={cy} r={5.2} fill={CYAN} />
          <circle cx={cx - 1.6} cy={cy - 1.8} r={1.4} fill="white" opacity={0.85} />
        </motion.g>
      );
  }
}

export function Eyes({ expression }: { expression: Expression }) {
  const closed = useBlink(expression === "normal");
  return (
    <g filter="url(#nexus-eye-glow)">
      <Eye cx={40} cy={37} expression={expression} closed={closed} />
      <Eye cx={60} cy={37} expression={expression} closed={closed} />
    </g>
  );
}
