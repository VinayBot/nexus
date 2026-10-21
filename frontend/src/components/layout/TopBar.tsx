"use client";

import { useQuery } from "@tanstack/react-query";
import { Moon, Settings2, Sun, Volume2, VolumeX, Zap, ZapOff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useUi } from "@/stores/ui";
import { useLive } from "@/stores/live";
import { useTour } from "@/stores/tour";
import { ApprovalsWaiting } from "@/components/approvals/ApprovalPrompt";
import { SystemPower } from "./SystemPower";
import { UserMenu } from "./UserMenu";
import { MissionSwitcher } from "./MissionSwitcher";

interface Readiness {
  status: "ok" | "degraded" | "down";
  checks: { name: string; status: string; detail: string }[];
}

/** One dot for "is everything connected": the backend's readiness plus the live event stream. */
function SystemStatus() {
  const socket = useLive((s) => s.socket);
  const { data, isError } = useQuery({
    queryKey: ["ready"],
    queryFn: () => get<Readiness>("/health/ready"),
    refetchInterval: 10_000,
  });
  const backend = isError ? "down" : (data?.status ?? "down");
  const status = backend === "down" ? "down" : backend === "degraded" || socket !== "open" ? "degraded" : "ok";
  const color = { ok: "var(--success)", degraded: "var(--warning)", down: "var(--error)" }[status];
  const detail = [
    `Live stream: ${socket}`,
    ...(isError
      ? ["Backend unreachable"]
      : (data?.checks.map((c) => `${c.name}: ${c.status} — ${c.detail}`) ?? ["checking…"])),
  ].join("\n");
  return (
    <span className="chip" title={detail} role="status" aria-label={`System ${status}`}>
      <span className="relative flex size-2">
        {status === "ok" && (
          <span className="absolute inset-0 animate-ping rounded-full opacity-60" style={{ background: color }} />
        )}
        <span
          className={cn("relative size-2 rounded-full", status !== "ok" && "animate-alarm")}
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
        />
      </span>
      {status === "ok" ? "Online" : status === "degraded" ? "Degraded" : "Offline"}
    </span>
  );
}

function Toggle({
  on,
  onClick,
  icon,
  label,
}: {
  on: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-muted hover:bg-surface-hover hover:text-text"
    >
      {icon}
      <span className="flex-1">{label}</span>
      <span className={cn("relative h-4 w-7 rounded-full transition-colors", on ? "bg-accent/70" : "bg-white/15")}>
        <span
          className={cn("absolute top-0.5 size-3 rounded-full bg-white transition-all", on ? "left-3.5" : "left-0.5")}
        />
      </span>
    </button>
  );
}

/** Theme, sound and performance tucked behind one gear button. */
function QuickSettings() {
  const { theme, toggleTheme, soundOn, toggleSound, performanceMode, togglePerformance } = useUi();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label="Display settings"
        className="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-hover hover:text-text"
      >
        <motion.span animate={{ rotate: open ? 90 : 0 }} className="grid place-items-center">
          <Settings2 className="size-4" />
        </motion.span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.16 }}
            className="glass absolute top-11 right-0 z-50 w-60 p-1.5"
          >
            <Toggle
              on={theme === "night"}
              onClick={toggleTheme}
              icon={theme === "night" ? <Moon className="size-4" /> : <Sun className="size-4" />}
              label="Night theme"
            />
            <Toggle
              on={soundOn}
              onClick={toggleSound}
              icon={soundOn ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
              label="Sound effects"
            />
            <Toggle
              on={performanceMode}
              onClick={togglePerformance}
              icon={performanceMode ? <ZapOff className="size-4" /> : <Zap className="size-4" />}
              label="Performance mode"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Loud badge whenever the backend runs on the scripted Simulation provider. */
function SimulationBadge() {
  const { data } = useQuery({
    queryKey: ["system-info"],
    queryFn: () => get<{ simulation: boolean }>("/system/info"),
    staleTime: 60_000,
  });
  if (!data?.simulation) return null;
  return (
    <span
      className="chip border-[#b8a7ff] font-semibold text-[#b8a7ff]"
      title="Scripted model responses — not live LLM output"
    >
      SIMULATION
    </span>
  );
}

export function TopBar() {
  return (
    <header className="panel relative z-30 mx-3 mt-3 flex h-14 shrink-0 items-center gap-2 px-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <MissionSwitcher />
      </div>
      <ApprovalsWaiting />
      <SimulationBadge />
      <SystemPower />
      <SystemStatus />
      <button
        type="button"
        onClick={() => useTour.getState().start(undefined, true)}
        className="btn btn-secondary btn-sm"
        title="Presentation mode: an auto-advancing guided tour"
      >
        ▶ Present
      </button>
      <QuickSettings />
      <UserMenu />
    </header>
  );
}
