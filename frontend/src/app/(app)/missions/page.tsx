"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LayoutGroup, motion } from "motion/react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { QuickApproval } from "@/components/approvals/QuickApproval";
import { MissionFloor } from "@/components/mission/MissionFloor";
import { MissionComposer } from "@/components/mission/MissionComposer";
import { MissionList } from "@/components/mission/MissionList";
import { ReportCard } from "@/components/mission/ReportCard";
import { StageStrip } from "@/components/mission/StageStrip";
import { ThoughtStream } from "@/components/mission/ThoughtStream";
import { Timeline } from "@/components/mission/Timeline";
import { WelcomeCard } from "@/components/mission/WelcomeCard";
import { useAgents } from "@/lib/agents";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { playbookName } from "@/lib/playbooks";
import { useApprovals, useMission, type Mission } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";
import { useMissionStream } from "@/stores/missionStream";
import { SPEEDS, useReplay } from "@/stores/replay";

const LiveGraph = dynamic(() => import("@/components/graph/LiveGraph").then((m) => m.LiveGraph), {
  ssr: false,
  loading: () => <div className="grid h-full place-items-center text-sm text-faint">Loading graph…</div>,
});

const STATUS_STYLE: Record<string, string> = {
  running: "bg-[rgb(var(--accent-rgb)/0.18)] text-accent",
  paused: "bg-warning/15 text-warning",
  completed: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  cancelled: "bg-white/5 text-muted",
  queued: "bg-white/5 text-muted",
  replay: "bg-[#b8a7ff]/15 text-[#b8a7ff]",
};
const STATUS_LABEL: Record<string, string> = { paused: "waiting for you" };

/** Turns a failure into something a person can act on. */
function explainError(error: string): string {
  if (/LLMUnavailableError|gave no answer|timeout/i.test(error))
    return "The local model did not answer in time. This usually means the Mac was short of memory or asleep. Close heavy apps, check that Ollama is running, then retry.";
  if (/token/i.test(error) && /cap|limit/i.test(error))
    return "The mission hit its token budget before finishing. Retry, or ask for something smaller.";
  if (/unreachable|ConnectError|connection/i.test(error))
    return "Ollama is not reachable. Start it (ollama serve) and retry.";
  return "Something went wrong inside the agent graph. The technical details are below. Retrying usually works.";
}

function FailureCard({ mission, onRetry }: { mission: Mission; onRetry: (m: Mission) => void }) {
  const qc = useQueryClient();
  const retry = useMutation({
    mutationFn: () =>
      post<Mission>("/missions", {
        task: mission.task,
        playbook: (mission.inputs?.playbook as string | undefined) ?? null,
        inputs: Object.fromEntries(
          Object.entries(mission.inputs ?? {}).filter(([k]) => !["started_at", "playbook"].includes(k)),
        ),
      } as never),
    onSuccess: (m) => {
      void qc.invalidateQueries({ queryKey: ["missions"] });
      onRetry(m);
    },
  });
  return (
    <section className="panel border-danger/40 p-4" aria-label="Mission failed">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-text">This mission stopped before finishing</h2>
          <p className="mt-1 text-sm text-muted">{explainError(mission.error ?? "")}</p>
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-faint">Technical details</summary>
            <pre className="mt-1 overflow-x-auto rounded-md bg-black/30 p-2 font-mono text-[11px] whitespace-pre-wrap text-faint">
              {mission.error}
            </pre>
          </details>
        </div>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => retry.mutate()}
          disabled={retry.isPending}
        >
          <RotateCcw className="size-3.5" /> Retry
        </button>
      </div>
    </section>
  );
}

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
  const approvals = useApprovals("pending");
  const approval = approvals.data?.find((a) => a.mission_id === missionId);
  const [mode, setMode] = useState<"floor" | "graph">("floor");
  const cancel = useMutation({ mutationFn: () => post(`/missions/${missionId}/cancel`) });
  const open = (id: string) => {
    setActive(id);
    router.push(`/missions?m=${id}`);
  };

  const status = replayOn ? "replay" : (mission.data?.status ?? (view.status !== "idle" ? view.status : "idle"));
  const m = mission.data;
  return (
    <div className="grid min-h-[640px] grid-cols-1 gap-3 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_330px]">
      <aside className="flex min-h-0 flex-col gap-3 lg:row-span-2 xl:sticky xl:top-0 xl:h-[calc(100dvh-6.5rem)]">
        <MissionComposer onCreated={(created) => open(created.id)} />
        <MissionList activeId={missionId} onSelect={open} />
      </aside>

      <section className="flex min-w-0 flex-col gap-3" aria-label="Mission">
        {!missionId ? (
          <WelcomeCard />
        ) : (
          <>
            <div className="panel flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <h1 className="truncate text-lg font-semibold text-text">{m?.title ?? view.title ?? "Mission"}</h1>
                <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span className={cn("rounded-full px-2 py-0.5 font-semibold capitalize", STATUS_STYLE[status])}>
                    {STATUS_LABEL[status] ?? status}
                  </span>
                  <span>{playbookName(m?.playbook)}</span>
                  {m?.source === "watcher" && <span className="text-warning">started by Hawk</span>}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setReplayOn((r) => !r)}
                  className={cn("btn btn-ghost btn-sm", replayOn && "!border-[#b8a7ff] !text-[#b8a7ff]")}
                  aria-pressed={replayOn}
                >
                  {replayOn ? "Back to live" : "Replay"}
                </button>
                {replayOn && (
                  <>
                    <button
                      type="button"
                      onClick={() => replay.setPlaying(!replay.playing)}
                      className="btn btn-ghost btn-sm"
                    >
                      {replay.playing ? "Pause" : "Play"}
                    </button>
                    <select
                      value={speed}
                      onChange={(e) => setSpeed(Number(e.target.value))}
                      className="rounded-md border border-border bg-black/30 px-1.5 py-1 text-xs"
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
                {status === "running" && !replayOn && (
                  <button
                    type="button"
                    onClick={() => cancel.mutate()}
                    className="btn btn-ghost btn-sm hover:!text-danger"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>

            <div className="panel px-2">
              <StageStrip view={view} />
            </div>

            {replayOn && (
              <div className="panel flex items-center gap-3 px-4 py-2 text-xs">
                <span className="font-semibold text-[#b8a7ff]">Replay</span>
                <span className="text-muted">Recorded events at {speed}×, not live.</span>
                <div className="h-1.5 flex-1 rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-[#b8a7ff]"
                    style={{
                      width: `${replay.progress.total ? (replay.progress.done / replay.progress.total) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {approval && !replayOn && (
              <motion.section
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="panel border-warning/40 p-4"
                aria-label="Your decision is needed"
                data-testid="inline-approval"
              >
                <QuickApproval approval={approval} />
              </motion.section>
            )}
            {m?.status === "failed" && !replayOn && <FailureCard mission={m} onRetry={(r) => open(r.id)} />}
            {m?.report && !replayOn && <ReportCard mission={m} />}

            <div className="panel overflow-hidden">
              <div className="flex items-center gap-2 border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold text-text">Agents at work</h2>
                <LayoutGroup>
                  <div className="ml-auto flex rounded-lg border border-border p-0.5" role="tablist" aria-label="View">
                    {(["floor", "graph"] as const).map((v) => (
                      <button
                        key={v}
                        type="button"
                        role="tab"
                        aria-selected={mode === v}
                        onClick={() => setMode(v)}
                        className="relative px-3 py-1 text-xs"
                      >
                        {mode === v && (
                          <motion.span
                            layoutId="view-toggle"
                            className="absolute inset-0 rounded-md bg-surface-hover"
                          />
                        )}
                        <span className={cn("relative", mode === v ? "text-text" : "text-faint")}>
                          {v === "floor" ? "Robots" : "Graph"}
                        </span>
                      </button>
                    ))}
                  </div>
                </LayoutGroup>
              </div>
              <motion.div layout className="relative h-[460px]" data-tour="mission-floor">
                <span key={`scan-${missionId}`} className="mission-scan" aria-hidden />
                {mode === "floor" ? (
                  <motion.div
                    key="floor"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-0"
                  >
                    <MissionFloor
                      key={`${missionId}-${replayOn}`}
                      view={view}
                      agents={agents.data}
                      className="h-full w-full"
                    />
                  </motion.div>
                ) : (
                  <motion.div
                    key="graph"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-0"
                  >
                    <LiveGraph view={view} />
                  </motion.div>
                )}
              </motion.div>
            </div>
            <Timeline view={view} />
          </>
        )}
      </section>

      <ThoughtStream
        view={view}
        agents={agents.data}
        className="min-h-[420px] lg:col-start-2 lg:h-[460px] xl:sticky xl:top-0 xl:col-start-3 xl:row-start-1 xl:h-[calc(100dvh-6.5rem)]"
      />
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
