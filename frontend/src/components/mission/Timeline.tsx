"use client";

import Link from "next/link";
import { motion } from "motion/react";
import type { MissionView } from "@/lib/missionView";

/** Checkpoints as glowing nodes along a line; each links to the Time Travel. */
export function Timeline({ view }: { view: MissionView }) {
  const cps = view.checkpoints;
  if (!view.missionId) return null;
  const shown = cps.slice(-80);
  return (
    <section className="panel flex items-center gap-3 px-3 py-2" aria-label="Checkpoint timeline">
      <span className="panel-title text-xs whitespace-nowrap text-gold">Checkpoints</span>
      <div className="relative flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-1">
        <span className="absolute inset-x-0 top-1/2 h-px bg-border" aria-hidden />
        {shown.length === 0 && (
          <span className="relative text-[11px] text-faint">Each super-step is saved to SQLite as it happens.</span>
        )}
        {shown.map((c, i) => (
          <motion.span key={c.id} initial={{ scale: 0 }} animate={{ scale: 1 }} className="relative">
            <Link
              href={`/timetravel/${view.missionId}?checkpoint=${c.id}`}
              title={`step ${c.step} → ${c.next.join(", ") || "end"}`}
              className="grid size-4 place-items-center rounded-[4px] border border-[#ff7b6b]/70 bg-[#8e1b17] text-[7px] text-[#ffd8cf] hover:scale-125"
              style={{ transform: `rotate(${(i % 3) - 1}deg)` }}
            >
              {c.step >= 0 ? c.step : "·"}
            </Link>
          </motion.span>
        ))}
      </div>
      <Link href={`/timetravel/${view.missionId}`} className="chip whitespace-nowrap hover:text-text">
        Time Travel →
      </Link>
    </section>
  );
}
