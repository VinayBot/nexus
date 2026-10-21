"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";
import { RoleGate } from "@/components/layout/RoleGate";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApprovals } from "@/lib/queries";

interface AuditEntry {
  id: number;
  ts: number;
  actor: string;
  channel: string;
  action: string;
  mission_id: string | null;
  detail: Record<string, unknown>;
}

export default function Page() {
  const [tab, setTab] = useState<"pending" | "history">("pending");
  const pending = useApprovals("pending");
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => get<AuditEntry[]>("/audit?limit=60"),
    enabled: tab === "history",
  });
  return (
    <>
      <PageHeader
        title="Approvals"
        description="Missions that need your decision wait here, with the full risk breakdown and evidence. You can also decide from the pop-up or a signed email link. Every decision is recorded in the audit log."
        actions={
          <div className="flex rounded-lg border border-border p-0.5" role="tablist">
            {(["pending", "history"] as const).map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs capitalize",
                  tab === t ? "bg-surface-hover text-text" : "text-faint",
                )}
              >
                {t === "pending" ? `Pending (${pending.data?.length ?? 0})` : "Audit log"}
              </button>
            ))}
          </div>
        }
      />
      {tab === "pending" ? (
        pending.isLoading ? (
          <EmptyState title="Loading…" />
        ) : pending.isError ? (
          <EmptyState title="Backend unreachable" tone="error" />
        ) : !pending.data?.length ? (
          <EmptyState title="Nothing to approve">
            Missions that need approval (risky actions, team designs, clarifying questions) will appear here and in your
            inbox.
          </EmptyState>
        ) : (
          <div className="space-y-4" data-tour="approvals-list">
            <RoleGate min="operator">
              {pending.data.map((a) => (
                <ApprovalCard key={a.id} approval={a} />
              ))}
            </RoleGate>
          </div>
        )
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-faint">
              <tr className="border-b border-border/50">
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2">Who</th>
                <th className="px-3 py-2">Channel</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Mission</th>
                <th className="px-3 py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {audit.data?.map((r) => (
                <tr key={r.id} className="border-b border-border/30 align-top">
                  <td className="px-3 py-2 whitespace-nowrap text-muted">{new Date(r.ts * 1000).toLocaleString()}</td>
                  <td className="px-3 py-2">{r.actor}</td>
                  <td className="px-3 py-2">
                    <span className="chip">{r.channel}</span>
                  </td>
                  <td className="px-3 py-2 text-gold">{r.action}</td>
                  <td className="px-3 py-2 font-mono text-faint">{r.mission_id ?? "—"}</td>
                  <td className="max-w-md truncate px-3 py-2 font-mono text-faint" title={JSON.stringify(r.detail)}>
                    {JSON.stringify(r.detail)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {audit.data?.length === 0 && <p className="p-4 text-sm text-faint">No decisions yet.</p>}
        </div>
      )}
    </>
  );
}
