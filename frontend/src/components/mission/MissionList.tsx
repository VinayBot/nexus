"use client";

import { cn } from "@/lib/cn";
import { useMissions, type Mission } from "@/lib/queries";

export const STATUS_COLOR: Record<Mission["status"], string> = {
  queued: "var(--text-faint)",
  running: "var(--cyan)",
  paused: "var(--error)",
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
      <h2 className="panel-title border-b border-border/60 px-3 py-2 text-sm text-gold">Missions</h2>
      <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {isLoading && <p className="p-3 text-xs text-faint">Loading…</p>}
        {isError && <p className="p-3 text-xs text-danger">Backend unreachable.</p>}
        {data?.length === 0 && (
          <p className="p-3 text-xs text-faint">No missions yet — begin one above, or arm a switch in the Chaos Lab.</p>
        )}
        <ul className="space-y-1">
          {data?.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => onSelect(m.id)}
                aria-current={m.id === activeId}
                className={cn(
                  "w-full rounded-lg border border-transparent px-2.5 py-2 text-left transition-colors hover:bg-surface-hover",
                  m.id === activeId && "border-border-strong bg-surface-hover",
                )}
              >
                <div className="flex items-center gap-2">
                  <StatusDot status={m.status} />
                  <span className="truncate text-[12.5px] text-text">{m.title}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 pl-4 text-[10.5px] text-faint">
                  <span>{m.playbook ?? "auto"}</span>
                  <span>·</span>
                  <span>
                    {m.status}
                    {m.outcome ? ` (${m.outcome})` : ""}
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
