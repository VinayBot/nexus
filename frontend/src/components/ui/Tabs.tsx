"use client";

import { motion } from "motion/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabDef {
  id: string;
  label: string;
  render: () => ReactNode;
}

/** URL-driven tabs (`?tab=`), with a sliding indicator and a fade between panels. */
export function UrlTabs({ tabs, layoutId }: { tabs: TabDef[]; layoutId: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const current = tabs.find((t) => t.id === params.get("tab")) ?? tabs[0]!;
  return (
    <>
      <div role="tablist" className="panel mb-4 inline-flex gap-1 p-1">
        {tabs.map((t) => {
          const active = t.id === current.id;
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() =>
                router.replace(t.id === tabs[0]!.id ? pathname : `${pathname}?tab=${t.id}`, { scroll: false })
              }
              className={cn(
                "relative rounded-lg px-4 py-1.5 text-sm transition-colors",
                active ? "text-text" : "text-muted hover:text-text",
              )}
            >
              {active && (
                <motion.span
                  layoutId={layoutId}
                  className="absolute inset-0 rounded-lg border border-border-strong bg-[color-mix(in_srgb,var(--sun-gold)_14%,transparent)]"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <span className="relative">{t.label}</span>
            </button>
          );
        })}
      </div>
      <motion.div
        key={current.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        {current.render()}
      </motion.div>
    </>
  );
}
