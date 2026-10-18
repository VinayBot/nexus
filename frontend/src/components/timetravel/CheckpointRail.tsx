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
/** Node colour by kind: fork violet, interrupt coral, verdict gold, plain checkpoint cyan. */
function nodeColor(c: { source?: string | null; interrupted?: boolean; has_verdict?: boolean }): string {
  if (c.source === "update") return "#8b7bff";
  if (c.interrupted) return "#ff4f6d";
  if (c.has_verdict) return "#ffb547";
  return "#4fe3f0";
}

export function CheckpointRail({
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
      <motion.div
        initial={{ clipPath: "inset(0 100% 0 0)" }}
        animate={{ clipPath: "inset(0 0% 0 0)" }}
        transition={{ duration: 1.1, ease: "easeOut" }}
        className="holo-grid overflow-x-auto rounded-lg border border-[rgb(139_151_255/0.2)] bg-[rgb(4_8_16/0.7)] text-text"
      >
        <svg width={layout.width} height={layout.height} className="block">
          {branches.map((b, i) => (
            <g key={b.head}>
              <text
                x={8}
                y={20 + i * LANE_H}
                fontSize={10}
                fill="#4fe3f0"
                fontWeight={600}
                fontFamily="var(--font-mono)"
                letterSpacing={1}
              >
                {b.label}
                {b.outcome ? ` · ${b.outcome}` : ""}
              </text>
              <line
                x1={30}
                x2={layout.width - 10}
                y1={36 + i * LANE_H}
                y2={36 + i * LANE_H}
                stroke="rgb(139 151 255 / 0.25)"
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
                stroke={split ? "#8b7bff" : "#4fe3f0"}
                style={{ filter: `drop-shadow(0 0 3px ${split ? "#8b7bff" : "#4fe3f0"})` }}
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
            return (
              <g
                key={c.checkpoint_id}
                transform={`translate(${q.x} ${q.y})`}
                className="cursor-pointer"
                onClick={() => onSelect(c.checkpoint_id)}
              >
                <title>{`step ${c.step} · ${c.writer ?? c.source} → ${c.next.join(", ") || "end"}`}</title>
                {sel && (
                  <circle
                    r={17}
                    fill="none"
                    stroke="#ffb547"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    className="spin-slow"
                  />
                )}
                <path
                  d="M0,-12 L10.4,-6 L10.4,6 L0,12 L-10.4,6 L-10.4,-6 Z"
                  fill={`${nodeColor(c)}33`}
                  stroke={sel ? "#ffb547" : nodeColor(c)}
                  strokeWidth={sel ? 2.2 : 1.4}
                  style={{ filter: `drop-shadow(0 0 ${sel ? 8 : 4}px ${sel ? "#ffb547" : nodeColor(c)})` }}
                />
                <text textAnchor="middle" dy={3.5} fontSize={9} fill="#eef1f8" fontWeight={700}>
                  {c.step ?? "·"}
                </text>
                <text textAnchor="middle" y={24} fontSize={8} fill="#a3abc2">
                  {(c.writer ?? c.source ?? "").replace("memory_write", "memory").slice(0, 9)}
                </text>
              </g>
            );
          })}
        </svg>
      </motion.div>
      <div className={cn("mt-2 flex flex-wrap gap-2 px-3 text-[10.5px] text-muted")}>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#4fe3f0]" /> checkpoint
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#ffb547]" /> has verdict
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#ff4f6d]" /> interrupt
        </span>
        <span className="chip">
          <span className="size-2 rounded-sm bg-[#8b7bff]" /> fork (update_state)
        </span>
      </div>
    </div>
  );
}
