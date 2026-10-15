"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { PanelIntro } from "@/components/ui/PageHeader";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { CURRICULUM } from "@/lib/curriculum";
import { useActiveMission } from "@/stores/missions";

const PER_MISSION = new Set(["/graph", "/timetravel", "/arena"]);

export function CurriculumPanel() {
  const evidence = useQuery({
    queryKey: ["curriculum-evidence"],
    queryFn: () => get<Record<string, number>>("/curriculum/evidence"),
  });
  const active = useActiveMission((st) => st.activeId);
  const href = (h: string) => (PER_MISSION.has(h) && active ? `${h}/${active}` : h);
  const seen = CURRICULUM.filter((c) => !c.evidence || (evidence.data?.[c.evidence] ?? 0) > 0).length;
  return (
    <>
      <PanelIntro
        title="Curriculum Map"
        description={`Every Week-4 topic, where it is implemented, and where to watch it. "Seen live" counts the real events of that kind recorded so far — ${seen}/${CURRICULUM.length} concepts have run on this machine.`}
      />
      <div className="panel overflow-x-auto" data-tour="curriculum">
        <table className="w-full text-left text-xs">
          <thead className="text-faint">
            <tr className="border-b border-border/50">
              <th className="px-3 py-2">Day</th>
              <th className="px-3 py-2">Concept</th>
              <th className="px-3 py-2">Implementation</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Where</th>
            </tr>
          </thead>
          <tbody>
            {CURRICULUM.map((c) => {
              const n = c.evidence ? (evidence.data?.[c.evidence] ?? 0) : null;
              return (
                <tr key={c.concept} className="border-b border-border/30 align-top">
                  <td className="px-3 py-2 font-display text-gold">{c.day}</td>
                  <td className="px-3 py-2">
                    <p className="text-sm text-text">{c.concept}</p>
                    <p className="text-faint">{c.topic}</p>
                    <p className="mt-1 max-w-md text-muted">{c.how}</p>
                  </td>
                  <td className="px-3 py-2 font-mono text-[10.5px] text-muted">
                    {c.code.map((x) => (
                      <div key={x}>{x}</div>
                    ))}
                  </td>
                  <td className="px-3 py-2">
                    <span className="chip border-success/60 text-success">implemented · tested</span>
                    {n !== null && (
                      <span className={cn("chip mt-1", n > 0 ? "border-accent/60 text-accent" : "text-faint")}>
                        {n > 0 ? `seen live · ${n.toLocaleString()} events` : "not run yet"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <p className="mb-1 text-muted">{c.screen}</p>
                    <Link href={href(c.href)} className="chip hover:text-text">
                      Show me →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
