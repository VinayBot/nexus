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
      <span className="panel-title shrink-0 text-xs whitespace-nowrap text-gold">Checkpoints</span>
      <div className="relative flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-1">
        <span className="absolute inset-x-0 top-1/2 h-px bg-border" aria-hidden />
        {shown.length === 0 && (
          <span className="relative text-[11px] text-faint">Each super-step is saved to SQLite as it happens.</span>
        )}
        {shown.map((c) => (
          <motion.span key={c.id} initial={{ scale: 0 }} animate={{ scale: 1 }} className="relative shrink-0">
            <Link
              href={`/timetravel/${view.missionId}?checkpoint=${c.id}`}
              title={`step ${c.step} → ${c.next.join(", ") || "end"}`}
              className="grid size-[18px] place-items-center rounded-[3px] border border-[rgb(79_227_240/0.6)] bg-[rgb(79_227_240/0.12)] font-mono text-[8px] text-[var(--cyan)] shadow-[0_0_8px_-2px_var(--cyan)] transition-transform hover:scale-125 hover:bg-[rgb(79_227_240/0.3)]"
            >
              {c.step >= 0 ? c.step : "·"}
            </Link>
          </motion.span>
        ))}
      </div>
      <Link href={`/timetravel/${view.missionId}`} className="btn btn-ghost btn-sm shrink-0">
        Time Travel →
      </Link>
    </section>
  );
}
