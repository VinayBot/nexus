"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useLive, type TickerItem } from "@/stores/live";

/** Global events as sliding holo-cards; approval requests pulse with a red beacon. */
export function Toasts() {
  const ticker = useLive((s) => s.ticker);
  const [shown, setShown] = useState<TickerItem[]>([]);
  const [seen, setSeen] = useState<string | null>(null);

  useEffect(() => {
    const last = ticker[ticker.length - 1];
    if (!last || last.id === seen) return;
    setSeen(last.id);
    setShown((s) => [...s.slice(-2), last]);
    const ttl = last.type === "interrupt.raised" ? 12000 : 5000;
    const t = setTimeout(() => setShown((s) => s.filter((x) => x.id !== last.id)), ttl);
    return () => clearTimeout(t);
  }, [ticker, seen]);

  return (
    <div className="pointer-events-none fixed top-20 right-4 z-[55] flex w-80 flex-col gap-2" aria-live="polite">
      <AnimatePresence>
        {shown.map((t) => {
          const alarm = t.type === "interrupt.raised" || t.type === "incident.detected";
          return (
            <motion.div
              key={t.id}
              initial={{ scaleY: 0, opacity: 0 }}
              animate={{ scaleY: 1, opacity: 1 }}
              exit={{ scaleY: 0, opacity: 0 }}
              style={{ transformOrigin: "top" }}
              className="pointer-events-auto relative rounded-md border-x-4 border-[#6b3a1c] bg-[linear-gradient(180deg,#efe2c4,#e3d1aa)] px-3 py-2 text-[12px] text-[#3b2410] shadow-xl"
            >
              <div className="flex items-start gap-2">
                <span
                  className={cn(
                    "mt-1 block size-2.5 shrink-0 rounded-full",
                    alarm ? "animate-alarm bg-[#c8341f]" : "bg-[#b07a1c]",
                  )}
                />
                <p className="flex-1">{t.text}</p>
              </div>
              {t.type === "interrupt.raised" && (
                <Link
                  href="/approvals"
                  className="mt-1 inline-block text-[11px] font-semibold text-[#8e1b17] underline"
                >
                  Review →
                </Link>
              )}
              {t.missionId && t.type !== "interrupt.raised" && (
                <Link
                  href={`/missions?m=${t.missionId}`}
                  className="mt-1 inline-block text-[11px] text-[#6b4a24] underline"
                >
                  Open mission
                </Link>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
