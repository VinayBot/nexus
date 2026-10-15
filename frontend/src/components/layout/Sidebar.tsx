"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ChevronsLeft, ChevronsRight } from "lucide-react";
import { useState } from "react";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/cn";
import { useUi } from "@/stores/ui";
import { useActiveMission } from "@/stores/missions";

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUi((s) => s.navCollapsed);
  const toggle = useUi((s) => s.toggleNav);
  const activeMission = useActiveMission((s) => s.activeId);
  const [moreOpen, setMoreOpen] = useState(false);
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <motion.nav
      aria-label="Primary"
      animate={{ width: collapsed ? 68 : 232 }}
      transition={{ type: "spring", stiffness: 320, damping: 34 }}
      className="panel z-20 m-3 mr-0 flex shrink-0 flex-col overflow-hidden"
    >
      <Link href="/" className="flex items-center gap-3 px-4 pt-4 pb-3" aria-label="NEXUS home">
        <span className="logo-core relative grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-[var(--sun-core)] to-[var(--ember)] font-display text-lg font-bold text-[var(--ink)] shadow-[var(--glow-gold)]">
          N
        </span>
        {!collapsed && <span className="font-display text-xl tracking-[0.2em] text-gold">NEXUS</span>}
      </Link>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {NAV.map((group) => (
          <div key={group.title} className="mt-3">
            {group.title === "More" ? (
              <button
                type="button"
                onClick={() => setMoreOpen((o) => !o)}
                aria-expanded={moreOpen}
                className="flex w-full items-center justify-between rounded-lg px-3 pb-1 text-[0.65rem] font-semibold tracking-[0.18em] text-faint uppercase hover:text-text"
              >
                {collapsed ? "···" : group.title}
                {!collapsed && (
                  <motion.span animate={{ rotate: moreOpen ? 180 : 0 }}>
                    <ChevronDown className="size-3.5" />
                  </motion.span>
                )}
              </button>
            ) : (
              !collapsed && (
                <p className="px-3 pb-1 text-[0.65rem] font-semibold tracking-[0.18em] text-faint uppercase">
                  {group.title}
                </p>
              )
            )}
            <AnimatePresence initial={false}>
              {(group.title !== "More" || moreOpen || group.items.some((i) => isActive(i.href))) && (
                <motion.ul
                  className="space-y-0.5 overflow-hidden"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22 }}
                >
                  {group.items.map((item) => {
                    const href = item.needsMission && activeMission ? `${item.href}/${activeMission}` : item.href;
                    const active = isActive(item.href);
                    const Icon = item.icon;
                    return (
                      <li key={item.href}>
                        <Link
                          href={href}
                          title={collapsed ? item.label : undefined}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface-hover hover:text-text",
                            active && "text-text",
                          )}
                        >
                          {active && (
                            <motion.span
                              layoutId="nav-active"
                              className="absolute inset-0 rounded-lg border border-border-strong bg-[color-mix(in_srgb,var(--sun-gold)_12%,transparent)]"
                              transition={{ type: "spring", stiffness: 400, damping: 36 }}
                            />
                          )}
                          <Icon
                            className={cn(
                              "relative size-4 shrink-0",
                              active ? "text-accent" : "text-faint group-hover:text-gold",
                            )}
                            aria-hidden
                          />
                          {!collapsed && <span className="relative truncate">{item.label}</span>}
                        </Link>
                      </li>
                    );
                  })}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={toggle}
        className="m-2 flex items-center justify-center gap-2 rounded-lg py-2 text-xs text-faint hover:bg-surface-hover hover:text-text"
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
      >
        {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
        {!collapsed && "Collapse"}
      </button>
    </motion.nav>
  );
}
