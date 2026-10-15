"use client";

import { motion } from "motion/react";
import { useMemo } from "react";
import { cn } from "@/lib/cn";

export interface CheckpointNode {
  checkpoint_id: string;
  parent_id: string | null;
  step: number | null;
  source: string | null;
  writer: string | null;
  next: string[];
  created_at: string | null;
  interrupted: boolean;
  outcome: string | null;
  has_verdict: boolean;
  plan_revision: number | null;
  branch: string | null;
}

export interface Branch {
  head: string;
  label: string;
  length: number;
  outcome: string | null;
}

const LANE_H = 64;
const STEP_W = 46;

/** The unrolled scroll: one lane per branch, seals per checkpoint, rivers at forks. */
export function ScrollOfTime({
  checkpoints,
  branches,
  selected,
  onSelect,
}: {
  checkpoints: CheckpointNode[];
  branches: Branch[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const layout = useMemo(() => {
    const lane: Record<string, number> = {};
    branches.forEach((b, i) => (lane[b.head] = i));
    const pos: Record<string, { x: number; y: number }> = {};
    checkpoints.forEach((c, i) => {
      const l = lane[c.branch ?? ""] ?? 0;
      pos[c.checkpoint_id] = { x: 40 + i * STEP_W, y: 36 + l * LANE_H };
    });
    return { pos, width: 80 + checkpoints.length * STEP_W, height: 50 + Math.max(1, branches.length) * LANE_H };
  }, [checkpoints, branches]);

  return (
    <div className="relative">
      {/* scroll rods */}
      <div className="absolute inset-y-0 left-0 z-10 w-3 rounded-full bg-gradient-to-r from-[#3b1d0f] to-[#6b3a1c] shadow-lg" />
      <div className="absolute inset-y-0 right-0 z-10 w-3 rounded-full bg-gradient-to-l from-[#3b1d0f] to-[#6b3a1c] shadow-lg" />
      <motion.div
        initial={{ clipPath: "inset(0 100% 0 0)" }}
        animate={{ clipPath: "inset(0 0% 0 0)" }}
        transition={{ duration: 1.1, ease: "easeOut" }}
        className="mx-2 overflow-x-auto rounded-md bg-[linear-gradient(180deg,#efe2c4,#e3d1aa)] text-[#3b2410] shadow-inner"
      >
        <svg width={layout.width} height={layout.height} className="block">
          {branches.map((b, i) => (
            <g key={b.head}>
              <text x={8} y={20 + i * LANE_H} fontSize={10} fill="#7a5530" fontWeight={600}>
                {b.label}
                {b.outcome ? ` · ${b.outcome}` : ""}
              </text>
              <line
                x1={30}
                x2={layout.width - 10}
                y1={36 + i * LANE_H}
                y2={36 + i * LANE_H}
                stroke="#b89a6a"
                strokeDasharray="2 6"
              />
            </g>
          ))}
          {/* rivers: parent → child links (curved where a branch splits off) */}
          {checkpoints.map((c) => {
            const p = c.parent_id ? layout.pos[c.parent_id] : undefined;
            const q = layout.pos[c.checkpoint_id];
            if (!p || !q) return null;
            const split = p.y !== q.y;
            return (
              <path
                key={`l-${c.checkpoint_id}`}
                d={
                  split
                    ? `M${p.x},${p.y} C${p.x + 30},${p.y} ${q.x - 30},${q.y} ${q.x},${q.y}`
                    : `M${p.x},${p.y} L${q.x},${q.y}`
                }
                stroke={split ? "#2f8fbf" : "#8e6a3c"}
                strokeWidth={split ? 3 : 2}
                fill="none"
                opacity={0.8}
              />
            );
          })}
          {checkpoints.map((c) => {
            const q = layout.pos[c.checkpoint_id];
            if (!q) return null;
            const sel = selected === c.checkpoint_id;
            const fork = c.source === "update";
            return (
              <g
                key={c.checkpoint_id}
                transform={`translate(${q.x} ${q.y})`}
                className="cursor-pointer"
                onClick={() => onSelect(c.checkpoint_id)}
              >
                <title>{`step ${c.step} · ${c.writer ?? c.source} → ${c.next.join(", ") || "end"}`}</title>
                <rect
                  x={-11}
                  y={-11}
                  width={22}
                  height={22}
                  rx={4}
                  transform={`rotate(${((c.step ?? 0) % 3) - 1})`}
                  fill={fork ? "#2f8fbf" : c.interrupted ? "#c8341f" : c.has_verdict ? "#b07a1c" : "#8e1b17"}
                  stroke={sel ? "#140909" : "rgba(255,255,255,0.4)"}
                  strokeWidth={sel ? 3 : 1}
                />
                <text textAnchor="middle" dy={3.5} fontSize={9} fill="#fff1e0" fontWeight={700}>
                  {c.step ?? "·"}
                </text>
                <text textAnchor="middle" y={24} fontSize={8} fill="#7a5530">
                  {(c.writer ?? c.source ?? "").replace("memory_write", "memory").slice(0, 9)}
                </text>
              </g>
            );
          })}
        </svg>
      </motion.div>
      <div className={cn("mt-2 flex flex-wrap gap-2 px-3 text-[10.5px] text-muted")}>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#8e1b17]" /> checkpoint
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#b07a1c]" /> has verdict
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#c8341f]" /> interrupt
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#2f8fbf]" /> fork (update_state)
        </span>
      </div>
    </div>
  );
}
