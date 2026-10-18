"use client";

import { AnimatePresence, motion } from "motion/react";
import { BellRing } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { create } from "zustand";
import { useApprovals } from "@/lib/queries";
import { QuickApproval } from "./QuickApproval";

/** Lets the top-bar button reopen the dialog for a given approval. */
export const useApprovalDialog = create<{ pinned: string | null; open: (id: string | null) => void }>()((set) => ({
  pinned: null,
  open: (id) => set({ pinned: id }),
}));

/** Top-bar button: how many decisions are waiting; click to review the newest. */
export function ApprovalsWaiting() {
  const pending = useApprovals("pending");
  const pathname = usePathname();
  const list = [...(pending.data ?? [])].sort((a, b) => b.created_at - a.created_at);
  if (!list.length || pathname.startsWith("/approvals")) return null;
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      onClick={() => useApprovalDialog.getState().open(list[0]?.id ?? null)}
      className="flex items-center gap-1.5 rounded-full border border-[rgb(251_191_36/0.4)] bg-warning/10 px-3 py-1 text-xs font-medium text-warning hover:bg-warning/20"
      aria-label={`${list.length} approval${list.length === 1 ? "" : "s"} waiting`}
    >
      <BellRing className="size-3.5" />
      {list.length} waiting
    </motion.button>
  );
}

/**
 * Human-in-the-loop on every screen. When a mission pauses for a decision, a dialog
 * opens over whatever page you are on, so you can approve without leaving it.
 * "Later" closes it; the "waiting" button in the top bar reopens it. Approvals that were
 * already waiting when the app opened only show that button (no surprise pop-ups).
 * The Approvals page lists the full cards, so the dialog stays out of the way there.
 */
export function ApprovalPrompt() {
  const pathname = usePathname();
  const pending = useApprovals("pending");
  const openedAt = useRef(Date.now() / 1000 - 5);
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const pinned = useApprovalDialog((st) => st.pinned);
  const setPinned = useApprovalDialog((st) => st.open);
  const list = useMemo(() => [...(pending.data ?? [])].sort((a, b) => b.created_at - a.created_at), [pending.data]);
  const fresh = list.find((a) => a.created_at >= openedAt.current && !dismissed.has(a.id));
  const current = list.find((a) => a.id === pinned) ?? fresh ?? null;
  const onApprovalsPage = pathname.startsWith("/approvals");
  const open = Boolean(current) && !onApprovalsPage;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && current) later(current.id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function later(id: string) {
    setDismissed((d) => new Set(d).add(id));
    setPinned(null);
  }

  return (
    <>
      <AnimatePresence>
        {open && current && (
          <motion.div
            key="approval-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[90] grid place-items-center bg-black/60 p-4"
            onMouseDown={(e) => e.target === e.currentTarget && later(current.id)}
          >
            <motion.div
              key={current.id}
              role="dialog"
              aria-modal="true"
              aria-label="Approval needed"
              initial={{ opacity: 0, y: 18, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className="panel w-full max-w-xl p-5"
            >
              <div className="mb-3 flex items-center gap-2">
                <span className="relative flex size-2">
                  <span className="absolute inset-0 animate-ping rounded-full bg-warning opacity-70" />
                  <span className="relative size-2 rounded-full bg-warning" />
                </span>
                <span className="text-xs font-semibold text-warning">Approval needed</span>
                {list.length > 1 && <span className="text-xs text-faint">· {list.length} waiting</span>}
                <button
                  type="button"
                  onClick={() => later(current.id)}
                  className="ml-auto rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-hover hover:text-text"
                >
                  Later
                </button>
              </div>
              <QuickApproval approval={current} onDone={() => later(current.id)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
