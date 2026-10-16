"use client";

import { useMutation } from "@tanstack/react-query";
import { LayoutGroup, motion } from "motion/react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { MissionFloor } from "@/components/mission/MissionFloor";
import { MissionComposer } from "@/components/mission/MissionComposer";
import { MissionList } from "@/components/mission/MissionList";
import { ReportCard } from "@/components/mission/ReportCard";
import { StageStrip } from "@/components/mission/StageStrip";
import { ThoughtStream } from "@/components/mission/ThoughtStream";
import { Timeline } from "@/components/mission/Timeline";
import { useAgents } from "@/lib/agents";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMission } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";
import { useMissionStream } from "@/stores/missionStream";
import { SPEEDS, useReplay } from "@/stores/replay";

const LiveGraph = dynamic(() => import("@/components/graph/LiveGraph").then((m) => m.LiveGraph), {
  ssr: false,
  loading: () => <div className="grid h-full place-items-center text-sm text-faint">Loading graph…</div>,
});

function MissionControl() {
  const params = useSearchParams();
  const router = useRouter();
  const { activeId, setActive } = useActiveMission();
  const fromUrl = params.get("m");
  useEffect(() => {
    if (fromUrl && fromUrl !== activeId) setActive(fromUrl);
  }, [fromUrl, activeId, setActive]);
  const missionId = fromUrl ?? activeId;
  const live = useMissionStream(missionId);
  const [replayOn, setReplayOn] = useState(false);
  const [speed, setSpeed] = useState(2);
  const replay = useReplay(missionId, replayOn, speed);
  useEffect(() => setReplayOn(false), [missionId]);
  const view = replayOn ? replay.view : live;
  const mission = useMission(missionId);
  const agents = useAgents();
  const [mode, setMode] = useState<"floor" | "graph">("floor");
  const cancel = useMutation({ mutationFn: () => post(`/missions/${missionId}/cancel`) });

  const status = replayOn ? "replay" : view.status !== "idle" ? view.status : (mission.data?.status ?? "idle");
  return (
    <div className="grid min-h-[640px] grid-cols-1 gap-3 lg:grid-cols-[260px_minmax(0,1fr)] xl:h-full xl:grid-cols-[280px_minmax(0,1fr)_330px] xl:grid-rows-[minmax(0,1fr)_auto]">
      <aside className="flex min-h-0 flex-col gap-3 lg:row-span-3 xl:row-span-2">
        <MissionComposer
          onCreated={(m) => {
            setActive(m.id);
            router.push(`/missions?m=${m.id}`);
          }}
        />
        <MissionList
          activeId={missionId}
          onSelect={(id) => {
            setActive(id);
            router.push(`/missions?m=${id}`);
          }}
        />
      </aside>

      <section className="flex min-h-0 flex-col gap-2 xl:overflow-hidden" aria-label="Command Center floor">
        <div className="panel flex flex-wrap items-center gap-2 px-3 py-2">
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-lg text-text">
              {mission.data?.title ?? view.title ?? "Mission Control"}
            </h1>
            <p className="text-[11px] text-faint">
              {missionId ? (
                <>
                  {mission.data?.playbook ?? "routing…"} · <span className="text-muted">{status}</span>
                  {mission.data?.outcome && ` · ${mission.data.outcome}`}
                </>
              ) : (
                "Choose a mission or begin a new one."
              )}
            </p>
          </div>
          {status === "paused" && (
            <Link
              href="/approvals"
              className="flex items-center gap-2 rounded-lg border border-danger bg-danger/20 px-3 py-1.5 text-xs font-semibold text-text"
            >
              <span className="animate-alarm block size-2 rounded-full bg-danger" />
              Awaiting your approval →
            </Link>
          )}
          {missionId && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setReplayOn((r) => !r)}
                className={cn("chip cursor-pointer", replayOn && "border-[#b8a7ff] text-[#b8a7ff]")}
                aria-pressed={replayOn}
              >
                {replayOn ? "■ Live" : "⏵ Replay"}
              </button>
              {replayOn && (
                <>
                  <button
                    type="button"
                    onClick={() => replay.setPlaying(!replay.playing)}
                    className="chip cursor-pointer"
                  >
                    {replay.playing ? "Pause" : "Play"}
                  </button>
                  <button type="button" onClick={replay.restart} className="chip cursor-pointer">
                    ⟲
                  </button>
                  <select
                    value={speed}
                    onChange={(e) => setSpeed(Number(e.target.value))}
                    className="rounded-md border border-border bg-black/40 px-1 py-0.5 text-xs"
                    aria-label="Replay speed"
                  >
                    {SPEEDS.map((s) => (
                      <option key={s} value={s}>
                        {s}×
                      </option>
                    ))}
                  </select>
                </>
              )}
            </div>
          )}
          {status === "running" && !replayOn && (
            <button type="button" onClick={() => cancel.mutate()} className="btn btn-ghost btn-sm hover:!text-danger">
              Cancel
            </button>
          )}
          <LayoutGroup>
            <div className="flex rounded-lg border border-border p-0.5" role="tablist" aria-label="View">
              {(["floor", "graph"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className="relative px-3 py-1 text-xs capitalize"
                >
                  {mode === m && (
                    <motion.span layoutId="view-toggle" className="absolute inset-0 rounded-md bg-surface-hover" />
                  )}
                  <span className={cn("relative", mode === m ? "text-text" : "text-faint")}>
                    {m === "floor" ? "Floor" : "Graph"}
                  </span>
                </button>
              ))}
            </div>
          </LayoutGroup>
        </div>
        <div className="panel px-2">
          <StageStrip view={view} />
        </div>
        {replayOn && (
          <div className="panel flex items-center gap-3 border-[#b8a7ff]/60 px-3 py-1.5 text-xs">
            <span className="rounded bg-[#b8a7ff]/20 px-2 font-semibold tracking-widest text-[#b8a7ff]">REPLAY</span>
            <span className="text-muted">Recorded events re-fed at {speed}× — not live.</span>
            <div className="h-1.5 flex-1 rounded-full bg-white/5">
              <div
                className="h-full rounded-full bg-[#b8a7ff]"
                style={{
                  width: `${replay.progress.total ? (replay.progress.done / replay.progress.total) * 100 : 0}%`,
                }}
              />
            </div>
            <span className="font-mono text-faint">
              {replay.progress.done}/{replay.progress.total}
            </span>
          </div>
        )}
        <motion.div layout className="relative min-h-[420px] flex-1" data-tour="mission-floor">
          <span key={`scan-${missionId ?? "none"}`} className="mission-scan" aria-hidden />
          {mode === "floor" ? (
            <motion.div
              key="floor"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="absolute inset-0"
            >
              <MissionFloor
                key={`${missionId ?? "none"}-${replayOn}`}
                view={view}
                agents={agents.data}
                className="h-full w-full"
              />
            </motion.div>
          ) : (
            <motion.div
              key="graph"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="absolute inset-0 overflow-hidden rounded-2xl border border-border bg-[color-mix(in_srgb,var(--ink)_85%,transparent)]"
            >
              <LiveGraph view={view} />
            </motion.div>
          )}
        </motion.div>
        {mission.data?.report && <ReportCard mission={mission.data} />}
      </section>

      <ThoughtStream
        view={view}
        agents={agents.data}
        className="min-h-[420px] lg:col-start-2 lg:h-[460px] xl:col-start-3 xl:row-span-2 xl:row-start-1 xl:h-auto"
      />
      <div className="lg:col-start-2 xl:row-start-2">
        <Timeline view={view} />
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <MissionControl />
    </Suspense>
  );
}
