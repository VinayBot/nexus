"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ChevronsLeft, ChevronsRight } from "lucide-react";
import { useState } from "react";
import { LogoMark, Wordmark } from "@/components/brand/Logo";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/cn";
import { useUi } from "@/stores/ui";
import { useActiveMission } from "@/stores/missions";
import { useApprovals } from "@/lib/queries";

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUi((s) => s.navCollapsed);
  const toggle = useUi((s) => s.toggleNav);
  const activeMission = useActiveMission((s) => s.activeId);
  const [moreOpen, setMoreOpen] = useState(false);
  const waiting = useApprovals("pending").data?.length ?? 0;
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <motion.nav
      aria-label="Primary"
      animate={{ width: collapsed ? 68 : 232 }}
      transition={{ type: "spring", stiffness: 320, damping: 34 }}
      className="panel z-20 m-3 mr-0 flex shrink-0 flex-col overflow-hidden"
    >
      <Link href="/" className="group flex items-center gap-3 px-4 pt-4 pb-3" aria-label="NEXUS home">
        <span className="transition-transform duration-500 group-hover:rotate-[60deg]">
          <LogoMark size={34} />
        </span>
        {!collapsed && (
          <span className="flex flex-col leading-none">
            <Wordmark className="text-xl" />
            <span className="mt-1 text-[11px] text-faint">Multi-agent workspace</span>
          </span>
        )}
      </Link>
      <div className="mx-4 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {NAV.map((group) => (
          <div key={group.title} className="mt-3">
            {group.title === "Advanced" ? (
              <button
                type="button"
                onClick={() => setMoreOpen((o) => !o)}
                aria-expanded={moreOpen}
                className="flex w-full items-center justify-between rounded-lg px-3 pb-1 text-xs font-medium text-faint hover:text-text"
              >
                {collapsed ? "···" : group.title}
                {!collapsed && (
                  <motion.span animate={{ rotate: moreOpen ? 180 : 0 }}>
                    <ChevronDown className="size-3.5" />
                  </motion.span>
                )}
              </button>
            ) : null}
            <AnimatePresence initial={false}>
              {(group.title !== "Advanced" || moreOpen || group.items.some((i) => isActive(i.href))) && (
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
                            "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted transition-[color,background-color,transform] duration-200 hover:translate-x-0.5 hover:bg-surface-hover hover:text-text",
                            active && "font-medium text-text",
                          )}
                        >
                          {active && (
                            <motion.span
                              layoutId="nav-active"
                              className="absolute inset-0 rounded-md bg-[rgb(var(--accent-rgb)/0.16)]"
                              transition={{ type: "spring", stiffness: 400, damping: 36 }}
                            >
                              <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-full bg-[var(--cyan)]" />
                            </motion.span>
                          )}
                          <Icon
                            className={cn(
                              "icon-pop relative size-4 shrink-0 transition-colors",
                              active ? "text-[var(--cyan)]" : "text-faint group-hover:text-accent",
                            )}
                            aria-hidden
                          />
                          {!collapsed && <span className="relative truncate">{item.label}</span>}
                          {item.href === "/approvals" && waiting > 0 && (
                            <span
                              className={cn(
                                "relative rounded-full bg-warning px-1.5 text-[10px] leading-4 font-bold text-black",
                                collapsed ? "absolute top-1 right-1" : "ml-auto",
                              )}
                              aria-label={`${waiting} waiting`}
                            >
                              {waiting}
                            </span>
                          )}
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
