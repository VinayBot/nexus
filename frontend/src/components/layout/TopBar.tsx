"use client";

import { useQuery } from "@tanstack/react-query";
import { Moon, Sun, Volume2, VolumeX, Zap, ZapOff } from "lucide-react";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useUi } from "@/stores/ui";

interface Readiness {
  status: "ok" | "degraded" | "down";
  checks: { name: string; status: string; detail: string }[];
}

function IconToggle({
  on,
  onClick,
  label,
  iconOn,
  iconOff,
}: {
  on: boolean;
  onClick: () => void;
  label: string;
  iconOn: React.ReactNode;
  iconOff: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      aria-label={label}
      title={label}
      className="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-hover hover:text-text"
    >
      {on ? iconOn : iconOff}
    </button>
  );
}

/** Backend readiness as a lantern: lit jade when ready, amber when degraded, red when down. */
export function BackendLantern() {
  const { data, isError } = useQuery({
    queryKey: ["ready"],
    queryFn: () => get<Readiness>("/health/ready"),
    refetchInterval: 10_000,
  });
  const status = isError ? "down" : (data?.status ?? "down");
  const color = { ok: "var(--success)", degraded: "var(--warning)", down: "var(--error)" }[status];
  const detail = isError
    ? "Backend unreachable"
    : (data?.checks.map((c) => `${c.name}: ${c.status} — ${c.detail}`).join("\n") ?? "checking…");
  return (
    <span className="chip" title={detail} role="status" aria-label={`Backend ${status}`}>
      <span
        className={cn("size-2 rounded-full", status !== "ok" && "animate-alarm")}
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
      {status === "ok" ? "Backend ready" : status === "degraded" ? "Degraded" : "Backend down"}
    </span>
  );
}

export function TopBar({ children }: { children?: React.ReactNode }) {
  const { theme, toggleTheme, soundOn, toggleSound, performanceMode, togglePerformance } = useUi();
  return (
    <header className="panel mx-3 mt-3 flex h-14 shrink-0 items-center gap-3 px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">{children}</div>
      <BackendLantern />
      <div className="flex items-center gap-0.5">
        <IconToggle
          on={theme === "night"}
          onClick={toggleTheme}
          label={theme === "night" ? "Switch to sunset theme" : "Switch to night theme"}
          iconOn={<Moon className="size-4" />}
          iconOff={<Sun className="size-4" />}
        />
        <IconToggle
          on={soundOn}
          onClick={toggleSound}
          label={soundOn ? "Mute sounds" : "Enable sounds"}
          iconOn={<Volume2 className="size-4" />}
          iconOff={<VolumeX className="size-4" />}
        />
        <IconToggle
          on={performanceMode}
          onClick={togglePerformance}
          label={performanceMode ? "Disable performance mode" : "Enable performance mode"}
          iconOn={<ZapOff className="size-4" />}
          iconOff={<Zap className="size-4" />}
        />
      </div>
    </header>
  );
}
