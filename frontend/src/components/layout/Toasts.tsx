"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useLive, type TickerItem } from "@/stores/live";

/** Approval requests have their own pop-up, and outbox lines are noise for a person. */
const SKIP = (t: TickerItem) => t.type === "interrupt.raised" || /outbox/i.test(t.text);

/**
 * Global notifications: solid, compact cards in the bottom-right corner (above the
 * guide button), at most two at a time, each closable. They never cover the main
 * columns' headers the way the old top-right stack did.
 */
export function Toasts() {
  const ticker = useLive((s) => s.ticker);
  const [shown, setShown] = useState<TickerItem[]>([]);
  const [seen, setSeen] = useState<string | null>(null);

  useEffect(() => {
    const last = ticker[ticker.length - 1];
    if (!last || last.id === seen) return;
    setSeen(last.id);
    if (SKIP(last)) return;
    setShown((s) => [...s.slice(-1), last]);
    const t = setTimeout(() => setShown((s) => s.filter((x) => x.id !== last.id)), 5000);
    return () => clearTimeout(t);
  }, [ticker, seen]);

  return (
    <div
      className="pointer-events-none fixed right-4 bottom-24 z-[55] flex w-[320px] max-w-[calc(100vw-2rem)] flex-col gap-2"
      aria-live="polite"
    >
      <AnimatePresence initial={false}>
        {shown.map((t) => {
          const alarm = t.type === "incident.detected" || /failed|rolled/i.test(t.text);
          const good = /success|completed|approved/i.test(t.text) && !alarm;
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ y: 16, opacity: 0, scale: 0.98 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ x: 40, opacity: 0 }}
              transition={{ type: "spring", stiffness: 340, damping: 30 }}
              className="pointer-events-auto flex items-start gap-3 rounded-xl border border-border bg-[var(--surface-strong)] px-3.5 py-3 text-sm shadow-[0_16px_40px_-16px_rgb(0_0_0/0.9)]"
            >
              <span
                className={cn(
                  "mt-1.5 size-2 shrink-0 rounded-full",
                  alarm ? "bg-danger" : good ? "bg-success" : "bg-[var(--cyan)]",
                )}
              />
              <div className="min-w-0 flex-1">
                <p className="leading-snug text-text">{t.text}</p>
                {t.missionId && (
                  <Link
                    href={`/missions?m=${t.missionId}`}
                    className="mt-1 inline-block text-xs text-accent hover:underline"
                  >
                    Open mission
                  </Link>
                )}
              </div>
              <button
                type="button"
                aria-label="Dismiss"
                onClick={() => setShown((s) => s.filter((x) => x.id !== t.id))}
                className="-mt-0.5 -mr-1 rounded-md p-1 text-faint hover:bg-surface-hover hover:text-text"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
