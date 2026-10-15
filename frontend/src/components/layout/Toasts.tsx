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
              layout
              initial={{ x: 60, opacity: 0, filter: "blur(6px)" }}
              animate={{ x: 0, opacity: 1, filter: "blur(0px)" }}
              exit={{ x: 60, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
              className={cn(
                "glass pointer-events-auto relative overflow-hidden border-l-2 px-3 py-2.5 text-[12px] text-text",
                alarm ? "border-l-[var(--danger)]" : "border-l-[var(--cyan)]",
              )}
            >
              <div className="flex items-start gap-2">
                <span
                  className={cn(
                    "mt-1 block size-2.5 shrink-0 rounded-full",
                    alarm
                      ? "animate-alarm bg-danger shadow-[0_0_8px_var(--error)]"
                      : "bg-accent shadow-[0_0_8px_var(--cyan)]",
                  )}
                />
                <p className="flex-1">{t.text}</p>
              </div>
              {t.type === "interrupt.raised" && (
                <Link
                  href="/approvals"
                  className="mt-1 inline-block text-[11px] font-semibold text-[var(--sun-gold)] hover:underline"
                >
                  Review →
                </Link>
              )}
              {t.missionId && t.type !== "interrupt.raised" && (
                <Link
                  href={`/missions?m=${t.missionId}`}
                  className="mt-1 inline-block text-[11px] text-accent hover:underline"
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
