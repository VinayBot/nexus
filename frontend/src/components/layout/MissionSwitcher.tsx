"use client";

import { useRouter } from "next/navigation";
import { StatusDot } from "@/components/mission/MissionList";
import { useMissions } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";

export function MissionSwitcher() {
  const { data } = useMissions(20);
  const { activeId, setActive } = useActiveMission();
  const router = useRouter();
  const active = data?.find((m) => m.id === activeId);
  return (
    <label className="flex min-w-0 items-center gap-2">
      {active && <StatusDot status={active.status} />}
      <span className="sr-only">Active mission</span>
      <select
        value={activeId ?? ""}
        onChange={(e) => {
          setActive(e.target.value || null);
          if (e.target.value) router.push(`/missions?m=${e.target.value}`);
        }}
        className="max-w-[340px] min-w-0 truncate rounded-lg border border-border bg-black/30 px-2 py-1.5 text-xs text-text"
      >
        <option value="">No mission selected</option>
        {data?.map((m) => (
          <option key={m.id} value={m.id}>
            {m.status === "paused" ? "⏸ " : m.status === "running" ? "▶ " : ""}
            {m.title.slice(0, 60)}
          </option>
        ))}
      </select>
    </label>
  );
}
