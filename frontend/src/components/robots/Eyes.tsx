"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import type { Expression } from "@/lib/robotMachine";

/** Random blinking while the robot is in its neutral expression. */
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
          }, 120);
        },
        2400 + Math.random() * 4000,
      );
    };
    loop();
    return () => clearTimeout(t);
  }, [enabled]);
  return closed;
}

/** One LED eye inside the visor; shapes change with the expression. */
function Eye({
  cx,
  cy,
  expression,
  closed,
  color,
  side,
}: {
  cx: number;
  cy: number;
  expression: Expression;
  closed: boolean;
  color: string;
  side: -1 | 1;
}) {
  const glow = { stroke: color, strokeWidth: 2.6, strokeLinecap: "round" as const, fill: "none" };
  switch (expression) {
    case "happy":
      return <path d={`M${cx - 5},${cy + 1.5} Q${cx},${cy - 5} ${cx + 5},${cy + 1.5}`} {...glow} />;
    case "focused":
      return <rect x={cx - 5.5} y={cy - 1.2} width={11} height={2.4} rx={1.2} fill={color} />;
    case "sleepy":
      return <rect x={cx - 4.5} y={cy + 1} width={9} height={1.6} rx={0.8} fill={color} opacity={0.35} />;
    case "error":
      return (
        <g {...glow} strokeWidth={2.2}>
          <path d={`M${cx - 3.5},${cy - 3.5} L${cx + 3.5},${cy + 3.5}`} />
          <path d={`M${cx + 3.5},${cy - 3.5} L${cx - 3.5},${cy + 3.5}`} />
        </g>
      );
    case "confused":
      return (
        <motion.path
          d={`M${cx},${cy} m-1,0 a1,1 0 1,1 2,0 a2.5,2.5 0 1,1 -5,0 a4,4 0 1,1 8,0`}
          {...glow}
          strokeWidth={1.8}
          animate={{ rotate: 360 * side }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        />
      );
    case "thinking":
      return (
        <g>
          {[0, 1, 2].map((i) => (
            <motion.circle
              key={i}
              cx={cx - 3.5 + i * 3.5}
              cy={cy}
              r={1.3}
              fill={color}
              animate={{ opacity: [0.2, 1, 0.2] }}
              transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.15 }}
            />
          ))}
        </g>
      );
    default:
      return (
        <motion.g
          animate={{ scaleY: closed ? 0.15 : 1 }}
          transition={{ duration: 0.06 }}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        >
          <rect x={cx - 4.5} y={cy - 3} width={9} height={6} rx={3} fill={color} />
          <rect x={cx - 3} y={cy - 2} width={2.6} height={1.6} rx={0.8} fill="white" opacity={0.8} />
        </motion.g>
      );
  }
}

export function Eyes({ expression, color }: { expression: Expression; color: string }) {
  const closed = useBlink(expression === "normal");
  return (
    <g filter="url(#nexus-led-glow)">
      <Eye cx={41} cy={29} expression={expression} closed={closed} color={color} side={-1} />
      <Eye cx={59} cy={29} expression={expression} closed={closed} color={color} side={1} />
    </g>
  );
}
