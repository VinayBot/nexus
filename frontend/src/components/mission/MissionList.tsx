"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { del } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useCan } from "@/lib/me";
import { useActiveMission } from "@/stores/missions";
import { playbookName } from "@/lib/playbooks";
import { useMissions, type Mission } from "@/lib/queries";

export const STATUS_COLOR: Record<Mission["status"], string> = {
  queued: "var(--text-faint)",
  running: "var(--cyan)",
  paused: "var(--warning)",
  completed: "var(--success)",
  failed: "var(--error)",
  cancelled: "var(--text-faint)",
};

export function StatusDot({ status }: { status: Mission["status"] }) {
  return (
    <span
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        (status === "running" || status === "paused") && "dot-live",
      )}
      style={{ background: STATUS_COLOR[status], ["--ripple" as string]: STATUS_COLOR[status] }}
      aria-hidden
    />
  );
}

/** Filter chips: mission types grouped the way a person thinks about them. */
const FILTERS: { id: string; label: string; playbooks: string[] | null }[] = [
  { id: "all", label: "All", playbooks: null },
  { id: "tickets", label: "Tickets", playbooks: ["ticket_creator", "ticket_solver"] },
  { id: "pages", label: "Web pages", playbooks: ["web_builder"] },
  { id: "questions", label: "Questions", playbooks: ["council_qa", "dynamic"] },
  { id: "fixes", label: "Fixes", playbooks: ["self_healing"] },
  { id: "builds", label: "Builds", playbooks: ["project_builder"] },
];

export function MissionList({ activeId, onSelect }: { activeId: string | null; onSelect: (id: string) => void }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { data, isLoading, isError } = useMissions(30);
  const [filter, setFilter] = useState("all");
  const canDelete = useCan("owner");
  const [confirming, setConfirming] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => del(`/missions/${id}`),
    onSuccess: (_, id) => {
      setConfirming(null);
      if (id === activeId) {
        useActiveMission.getState().setActive(null);
        router.push("/missions");
      }
      void qc.invalidateQueries({ queryKey: ["missions"] });
      void qc.invalidateQueries({ queryKey: ["approvals"] });
    },
  });
  // only offer the filters that have missions, so the row stays short
  const present = new Set((data ?? []).map((m) => m.playbook ?? ""));
  const chips = FILTERS.filter((f) => !f.playbooks || f.playbooks.some((p) => present.has(p)));
  const chosen = FILTERS.find((f) => f.id === filter)?.playbooks;
  const shown = (data ?? []).filter((m) => !chosen || chosen.includes(m.playbook ?? ""));

  return (
    <section className="panel flex min-h-0 flex-col" aria-label="Missions">
      <h2 className="panel-title border-b border-border px-4 py-2.5 text-sm">Recent missions</h2>
      {chips.length > 2 && (
        <div
          className="flex flex-wrap gap-1 border-b border-border px-3 py-2"
          role="radiogroup"
          aria-label="Filter missions"
        >
          {chips.map((f) => (
            <button
              key={f.id}
              type="button"
              role="radio"
              aria-checked={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={cn("chip cursor-pointer", filter === f.id && "border-border-strong text-text")}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {isLoading && (
          <div className="space-y-2 p-1.5" aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-11" />
            ))}
          </div>
        )}
        {isError && <p className="p-3 text-xs text-danger">Backend unreachable.</p>}
        {data?.length === 0 && <p className="p-3 text-xs text-faint">No missions yet. Start one above.</p>}
        {data && data.length > 0 && shown.length === 0 && (
          <p className="p-3 text-xs text-faint">No missions of this type.</p>
        )}
        <ul className="space-y-1">
          <AnimatePresence initial={false}>
            {shown.map((m) => (
              <motion.li
                key={m.id}
                layout
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -24, height: 0, transition: { duration: 0.22 } }}
                className="group relative"
              >
                {confirming === m.id ? (
                  <div className="flex items-center gap-2 rounded-md border border-danger/40 bg-danger/10 px-2.5 py-2 text-xs">
                    <span className="min-w-0 flex-1 truncate text-text">Delete “{m.title}”?</span>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(m.id)}
                    >
                      {remove.isPending ? "Deleting…" : "Delete"}
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(null)}>
                      Keep
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => onSelect(m.id)}
                      aria-current={m.id === activeId}
                      className={cn(
                        "relative w-full overflow-hidden rounded-md border border-transparent py-2 pr-9 pl-2.5 text-left transition-[background-color,border-color,transform] duration-200 hover:translate-x-0.5 hover:bg-surface-hover",
                        m.id === activeId && "bg-[rgb(var(--accent-rgb)/0.12)] shadow-[inset_2px_0_0_var(--cyan)]",
                        m.status === "running" && "running-sheen",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <StatusDot status={m.status} />
                        <span className="truncate text-[12.5px] text-text">{m.title}</span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-2 pl-4 text-[10.5px] text-faint">
                        <span>{playbookName(m.playbook)}</span>
                        <span>·</span>
                        <span
                          className={cn(
                            m.status === "paused" && "text-warning",
                            m.status === "failed" && "text-danger",
                          )}
                        >
                          {m.status === "paused" ? "waiting for you" : m.status}
                          {m.outcome && m.outcome !== "success" ? ` (${m.outcome.replace("_", " ")})` : ""}
                        </span>
                        {m.source === "watcher" && <span className="text-warning">· Hawk</span>}
                      </div>
                    </button>
                    {canDelete && m.status !== "running" && m.status !== "queued" && (
                      <button
                        type="button"
                        onClick={() => setConfirming(m.id)}
                        aria-label={`Delete mission ${m.title}`}
                        className="absolute top-1/2 right-1.5 grid size-7 -translate-y-1/2 place-items-center rounded-md text-faint opacity-0 transition-opacity group-hover:opacity-100 hover:bg-danger/15 hover:text-danger focus-visible:opacity-100"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    )}
                  </>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </section>
  );
}
