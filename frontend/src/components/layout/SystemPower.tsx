"use client";

import * as Popover from "@radix-ui/react-popover";
import { Cpu } from "lucide-react";
import { cn } from "@/lib/cn";
import { useLive } from "@/stores/live";

/** "System Power": live Resource Governor gauge (RAM, models, queue, tokens/sec). */
export function SystemPower() {
  const g = useLive((s) => s.governor);
  const pct = g ? Math.round(g.ram_percent) : 0;
  const color = !g
    ? "var(--text-faint)"
    : g.pressure === "critical"
      ? "var(--error)"
      : g.pressure === "elevated"
        ? "var(--warning)"
        : "var(--success)";
  const arc = 2 * Math.PI * 13;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="chip cursor-pointer gap-2 py-1 hover:text-text"
          aria-label="System Power: resource governor"
          data-tour="system-power"
        >
          <svg viewBox="0 0 32 32" className="size-6 -rotate-90" aria-hidden>
            <circle cx="16" cy="16" r="13" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="4" />
            <circle
              cx="16"
              cy="16"
              r="13"
              fill="none"
              stroke={color}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${(pct / 100) * arc} ${arc}`}
              style={{ transition: "stroke-dasharray .6s" }}
            />
          </svg>
          <span className="text-left leading-tight">
            <span className="block text-[10px] text-faint">System Power</span>
            <span className="block font-mono text-[11px] text-text">
              {g ? `${g.ram_available_gb.toFixed(1)} GB free · ${g.tokens_per_sec} t/s` : "—"}
            </span>
          </span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content sideOffset={8} className="panel z-50 w-72 p-3 text-xs">
          <p className="panel-title mb-2 flex items-center gap-1.5 text-sm text-gold">
            <Cpu className="size-4" /> Resource Governor
          </p>
          {!g ? (
            <p className="text-faint">Waiting for metrics…</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <dt className="text-faint">RAM used</dt>
              <dd className="font-mono">
                {g.ram_percent}% of {g.ram_total_gb} GB
              </dd>
              <dt className="text-faint">Pressure</dt>
              <dd className={cn("font-mono", g.pressure !== "normal" && "text-warning")}>{g.pressure}</dd>
              <dt className="text-faint">LLM slots</dt>
              <dd className="font-mono">
                {g.in_flight} / {g.limit} (cfg {g.configured_limit})
              </dd>
              <dt className="text-faint">Queued calls</dt>
              <dd className="font-mono">{g.queue_depth}</dd>
              <dt className="text-faint">Tokens / sec</dt>
              <dd className="font-mono">{g.tokens_per_sec}</dd>
              <dt className="col-span-2 mt-1 text-faint">Loaded models</dt>
              {g.loaded_models.length === 0 && <dd className="col-span-2 text-faint">none (unloaded after idle)</dd>}
              {g.loaded_models.map((m) => (
                <dd key={String(m.name)} className="col-span-2 font-mono">
                  {String(m.name)} · {String(m.size_gb)} GB
                </dd>
              ))}
            </dl>
          )}
          <p className="mt-2 text-[10.5px] text-faint">
            Under memory pressure the governor lowers concurrency and queues work instead of failing.
          </p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
