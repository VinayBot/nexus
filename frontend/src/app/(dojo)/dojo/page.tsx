"use client";

import { useMutation } from "@tanstack/react-query";
import { LayoutGroup, motion } from "motion/react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DojoFloor } from "@/components/dojo/DojoFloor";
import { MissionComposer } from "@/components/dojo/MissionComposer";
import { MissionList } from "@/components/dojo/MissionList";
import { ReportCard } from "@/components/dojo/ReportCard";
import { StageStrip } from "@/components/dojo/StageStrip";
import { ThoughtStream } from "@/components/dojo/ThoughtStream";
import { Timeline } from "@/components/dojo/Timeline";
import { useAgents } from "@/lib/agents";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMission } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";
import { useMissionStream } from "@/stores/missionStream";

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
  const view = useMissionStream(missionId);
  const mission = useMission(missionId);
  const agents = useAgents();
  const [mode, setMode] = useState<"dojo" | "graph">("dojo");
  const cancel = useMutation({ mutationFn: () => post(`/missions/${missionId}/cancel`) });

  const status = view.status !== "idle" ? view.status : (mission.data?.status ?? "idle");
  return (
    <div className="grid h-full min-h-[640px] grid-cols-1 gap-3 lg:grid-cols-[290px_minmax(0,1fr)_340px] lg:grid-rows-[minmax(0,1fr)_auto]">
      <aside className="flex min-h-0 flex-col gap-3 lg:row-span-2">
        <MissionComposer
          onCreated={(m) => {
            setActive(m.id);
            router.push(`/dojo?m=${m.id}`);
          }}
        />
        <MissionList
          activeId={missionId}
          onSelect={(id) => {
            setActive(id);
            router.push(`/dojo?m=${id}`);
          }}
        />
      </aside>

      <section className="flex min-h-0 flex-col gap-2" aria-label="Dojo floor">
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
              className="animate-alarm rounded-lg border border-danger bg-danger/20 px-3 py-1.5 text-xs font-semibold text-text"
            >
              Awaiting your seal →
            </Link>
          )}
          {status === "running" && (
            <button type="button" onClick={() => cancel.mutate()} className="chip cursor-pointer hover:text-danger">
              Cancel
            </button>
          )}
          <LayoutGroup>
            <div className="flex rounded-lg border border-border p-0.5" role="tablist" aria-label="View">
              {(["dojo", "graph"] as const).map((m) => (
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
                    {m === "dojo" ? "Dojo" : "Graph"}
                  </span>
                </button>
              ))}
            </div>
          </LayoutGroup>
        </div>
        <div className="panel px-2">
          <StageStrip view={view} />
        </div>
        <motion.div layout className="relative min-h-[420px] flex-1">
          {mode === "dojo" ? (
            <motion.div
              key="dojo"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="absolute inset-0"
            >
              <DojoFloor key={missionId ?? "none"} view={view} agents={agents.data} className="h-full w-full" />
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

      <ThoughtStream view={view} agents={agents.data} className="min-h-[420px] lg:row-span-2" />
      <div className="lg:col-start-2">
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
