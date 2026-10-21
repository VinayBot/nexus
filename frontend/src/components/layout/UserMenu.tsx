"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { clearToken } from "@/lib/auth";
import { ROLE_LABEL, useMe } from "@/lib/me";

/** Who is signed in, their role, and Sign out. Hidden when auth is off. */
export function UserMenu() {
  const me = useMe().data;
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  if (!me?.auth_enabled) return null;
  const signOut = () => {
    clearToken();
    qc.clear();
    router.replace("/login");
  };
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Account: ${me.username}`}
        className="flex items-center gap-2 rounded-full border border-border py-1 pr-3 pl-1 text-xs text-text hover:border-white/20"
      >
        <span className="grid size-6 place-items-center rounded-full bg-[var(--accent-strong)] text-[11px] font-bold text-white uppercase">
          {me.username.slice(0, 1)}
        </span>
        {me.username}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6 }}
            className="glass absolute top-10 right-0 z-50 w-56 p-2"
          >
            <p className="px-2 pt-1 text-sm font-medium text-text">{me.username}</p>
            <p className="px-2 pb-2 text-xs text-muted">Role: {ROLE_LABEL[me.role]}</p>
            {Boolean(me.daily_token_quota) && (
              <QuotaBar used={me.tokens_today ?? 0} quota={me.daily_token_quota ?? 0} />
            )}
            <button
              type="button"
              onClick={signOut}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted hover:bg-surface-hover hover:text-text"
            >
              <LogOut className="size-4" /> Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Model tokens this account used in the last 24 hours, against its daily quota. */
function QuotaBar({ used, quota }: { used: number; quota: number }) {
  const share = Math.min(1, used / quota);
  return (
    <div className="px-2 pb-2" aria-label="Tokens used today">
      <div className="flex justify-between text-[11px] text-faint">
        <span>Tokens today</span>
        <span>
          {used.toLocaleString()} / {quota.toLocaleString()}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${share * 100}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
          className={share > 0.9 ? "h-full bg-danger" : "h-full bg-[var(--accent-strong)]"}
        />
      </div>
    </div>
  );
}
