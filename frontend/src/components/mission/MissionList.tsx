"use client";

import { cn } from "@/lib/cn";
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
        (status === "running" || status === "paused") && "animate-glow",
      )}
      style={{ background: STATUS_COLOR[status], boxShadow: `0 0 8px ${STATUS_COLOR[status]}` }}
      aria-hidden
    />
  );
}

export function MissionList({ activeId, onSelect }: { activeId: string | null; onSelect: (id: string) => void }) {
  const { data, isLoading, isError } = useMissions(30);
  return (
    <section className="panel flex min-h-0 flex-col" aria-label="Missions">
      <h2 className="panel-title border-b border-border px-4 py-2.5 text-sm">Recent missions</h2>
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
        <ul className="stagger space-y-1">
          {data?.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => onSelect(m.id)}
                aria-current={m.id === activeId}
                className={cn(
                  "relative w-full overflow-hidden rounded-md border border-transparent px-2.5 py-2 text-left transition-[background-color,border-color,transform] duration-200 hover:translate-x-0.5 hover:bg-surface-hover",
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
                  <span className={cn(m.status === "paused" && "text-warning", m.status === "failed" && "text-danger")}>
                    {m.status === "paused" ? "waiting for you" : m.status}
                    {m.outcome && m.outcome !== "success" ? ` (${m.outcome.replace("_", " ")})` : ""}
                  </span>
                  {m.source === "watcher" && <span className="text-warning">· Hawk</span>}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
