"use client";

import dynamic from "next/dynamic";
import { use } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { useMission } from "@/lib/queries";
import { useMissionStream } from "@/stores/missionStream";

const LiveGraph = dynamic(() => import("@/components/graph/LiveGraph").then((m) => m.LiveGraph), { ssr: false });

export default function Page({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = use(params);
  const view = useMissionStream(missionId);
  const mission = useMission(missionId);
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Live Graph"
        kanji="流れ"
        description={
          <>
            The compiled LangGraph for <span className="text-text">{mission.data?.title ?? missionId}</span>. Lit
            lanterns are running nodes; light flows along the branch just taken; ×N counts cycle iterations; the State
            Inspector shows which reducer merged each parallel update.
          </>
        }
      />
      <div className="panel min-h-[560px] flex-1 overflow-hidden">
        <LiveGraph view={view} showInspector />
      </div>
    </div>
  );
}
