import { cn } from "@/lib/cn";
import type { MissionView } from "@/lib/missionView";
import { STAGES } from "./layout";

/** Mini-map of the main graph: which stage is lit right now, which are done. */
export function StageStrip({ view }: { view: MissionView }) {
  return (
    <ol className="flex items-center gap-1 overflow-x-auto px-1 py-1" aria-label="Mission stages">
      {STAGES.map((s, i) => {
        const n = view.nodes[s.id] ?? (s.id === "council" ? view.nodes.synthesize : undefined);
        const active = view.currentNode === s.id || n?.status === "active";
        const done = n?.status === "done";
        const error = n?.status === "error";
        const waiting = n?.status === "interrupted";
        return (
          <li key={s.id} className="flex items-center gap-1">
            {i > 0 && (
              <span className="relative h-px w-3 overflow-hidden bg-border">
                <span
                  className={cn(
                    "absolute inset-0 origin-left bg-[var(--cyan)] shadow-[0_0_6px_var(--cyan)] transition-transform duration-500",
                    done || active ? "scale-x-100" : "scale-x-0",
                  )}
                />
              </span>
            )}
            <span
              className={cn(
                "relative flex items-center gap-1 overflow-hidden rounded-full border px-2 py-0.5 text-[10.5px] whitespace-nowrap transition-[color,border-color,box-shadow,background-color] duration-300",
                active && "stage-active border-accent bg-accent/15 text-text shadow-[var(--glow-cyan)]",
                done && !active && "border-[rgb(var(--accent-soft-rgb)/0.35)] text-accent",
                error && "border-danger text-danger",
                waiting && "animate-alarm border-danger text-danger",
                !active && !done && !error && !waiting && "border-border/50 text-faint",
              )}
            >
              {done && !active && <span aria-hidden>✓</span>}
              {s.label}
              {n && n.visits > 1 && <span className="font-mono text-[9px] text-muted">×{n.visits}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
