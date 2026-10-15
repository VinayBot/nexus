"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, use, useEffect, useState } from "react";
import { ScrollOfTime, type Branch, type CheckpointNode } from "@/components/timetravel/ScrollOfTime";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { get, post } from "@/lib/api";
import { useMission } from "@/lib/queries";
import { useMissionStream } from "@/stores/missionStream";

interface History {
  checkpoints: CheckpointNode[];
  branches: Branch[];
}
interface Compared {
  head: string;
  steps: number;
  outcome: string | null;
  answer: string;
  winner: string | null;
  confidence: number | null;
  risk: string | null;
  execution: string | null;
  verification: string | null;
  plan_revision: number | null;
  started: string | null;
  finished: string | null;
}

const PATCH_EXAMPLES: Record<string, string> = {
  "Tighter ReAct loop": JSON.stringify({ limits: { react: 2 } }, null, 2),
  "More debate rounds": JSON.stringify({ limits: { debate: 2 } }, null, 2),
  "Change the task": JSON.stringify({ task: "Answer in exactly two sentences." }, null, 2),
};

function seconds(a: string | null, b: string | null): string {
  if (!a || !b) return "—";
  return `${((Date.parse(b) - Date.parse(a)) / 1000).toFixed(1)}s`;
}

function TimeTravel({ missionId }: { missionId: string }) {
  const qc = useQueryClient();
  const params = useSearchParams();
  const view = useMissionStream(missionId);
  const mission = useMission(missionId);
  const history = useQuery({
    queryKey: ["history", missionId, view.checkpoints.length],
    queryFn: () => get<History>(`/missions/${missionId}/history`),
  });
  const [selected, setSelected] = useState<string | null>(params.get("checkpoint"));
  const [patch, setPatch] = useState(PATCH_EXAMPLES["Tighter ReAct loop"]!);
  const [asNode, setAsNode] = useState("");
  const [cmp, setCmp] = useState<[string, string] | null>(null);
  useEffect(() => {
    if (!selected && history.data?.checkpoints.length)
      setSelected(history.data.checkpoints[history.data.checkpoints.length - 1]!.checkpoint_id);
  }, [history.data, selected]);

  const state = useQuery({
    queryKey: ["checkpoint", missionId, selected],
    queryFn: () =>
      get<{ summary: CheckpointNode; values: Record<string, unknown> }>(
        `/missions/${missionId}/checkpoints/${selected}`,
      ),
    enabled: Boolean(selected),
  });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["history", missionId] });
    void qc.invalidateQueries({ queryKey: ["missions"] });
  };
  const rerun = useMutation({
    mutationFn: () => post(`/missions/${missionId}/rerun`, { checkpoint_id: selected }),
    onSuccess: refresh,
  });
  const fork = useMutation({
    mutationFn: () =>
      post(`/missions/${missionId}/fork`, {
        checkpoint_id: selected,
        patch: JSON.parse(patch),
        as_node: asNode || null,
      }),
    onSuccess: refresh,
  });
  const runnerUp = useMutation({ mutationFn: () => post(`/missions/${missionId}/runner-up`), onSuccess: refresh });
  const compare = useQuery({
    queryKey: ["compare", missionId, cmp],
    queryFn: () =>
      get<{ a: Compared; b: Compared; fork_point: string | null }>(
        `/missions/${missionId}/compare?a=${cmp![0]}&b=${cmp![1]}`,
      ),
    enabled: Boolean(cmp),
  });

  const branches = history.data?.branches ?? [];
  const running = view.status === "running";
  const values = state.data?.values ?? {};
  return (
    <>
      <PageHeader
        title="Scroll of Time"
        kanji="時"
        description={
          <>
            Every super-step of <span className="text-text">{mission.data?.title ?? missionId}</span> is a checkpoint in
            SQLite. Inspect any of them, re-run from it, or fork by editing state (<code>update_state</code>) — the new
            branch splits off like a river.
          </>
        }
      />
      {history.isLoading ? (
        <EmptyState title="Unrolling the scroll…" />
      ) : !history.data?.checkpoints.length ? (
        <EmptyState title="No checkpoints yet" />
      ) : (
        <div className="space-y-3">
          <div className="panel p-3">
            <ScrollOfTime
              checkpoints={history.data.checkpoints}
              branches={branches}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_380px]">
            <section className="panel min-w-0 p-3">
              <h2 className="panel-title text-sm text-gold">
                Checkpoint {selected?.slice(-8)} · step {state.data?.summary.step} · written by{" "}
                {state.data?.summary.writer ?? "—"}
              </h2>
              <p className="text-xs text-faint">next: {state.data?.summary.next.join(", ") || "end"}</p>
              <pre className="mt-2 max-h-[420px] overflow-auto rounded-lg bg-black/40 p-2 font-mono text-[11px] text-muted">
                {JSON.stringify(values, null, 2)}
              </pre>
            </section>
            <aside className="space-y-3">
              <section className="panel space-y-2 p-3">
                <h3 className="panel-title text-sm text-gold">Travel</h3>
                {running && (
                  <p className="text-xs text-warning">
                    The mission is running — wait or cancel it before time travelling.
                  </p>
                )}
                <button
                  type="button"
                  disabled={running || !selected || rerun.isPending}
                  onClick={() => rerun.mutate()}
                  className="chip w-full cursor-pointer justify-center py-2 hover:text-text disabled:opacity-40"
                >
                  ⟲ Re-run from this checkpoint
                </button>
                <button
                  type="button"
                  disabled={running || runnerUp.isPending}
                  onClick={() => runnerUp.mutate()}
                  className="chip w-full cursor-pointer justify-center py-2 hover:text-text disabled:opacity-40"
                >
                  ⚖ Choose the tournament runner-up instead
                </button>
                {(rerun.error || runnerUp.error) && (
                  <p className="text-xs text-danger">{String((rerun.error ?? runnerUp.error)?.message)}</p>
                )}
              </section>
              <section className="panel space-y-2 p-3">
                <h3 className="panel-title text-sm text-gold">Fork with a state patch</h3>
                <div className="flex flex-wrap gap-1">
                  {Object.keys(PATCH_EXAMPLES).map((k) => (
                    <button
                      key={k}
                      type="button"
                      className="chip cursor-pointer"
                      onClick={() => setPatch(PATCH_EXAMPLES[k]!)}
                    >
                      {k}
                    </button>
                  ))}
                </div>
                <textarea
                  value={patch}
                  onChange={(e) => setPatch(e.target.value)}
                  rows={5}
                  className="w-full rounded-lg border border-border bg-black/50 p-2 font-mono text-[11px]"
                  aria-label="State patch JSON"
                />
                <input
                  value={asNode}
                  onChange={(e) => setAsNode(e.target.value)}
                  placeholder="as_node (optional, e.g. council)"
                  className="w-full rounded-lg border border-border bg-black/40 px-2 py-1.5 text-xs"
                />
                <button
                  type="button"
                  disabled={running || !selected || fork.isPending}
                  onClick={() => fork.mutate()}
                  data-tour="fork-button"
                  className="w-full rounded-lg bg-[#2f8fbf]/30 py-2 text-sm font-semibold text-text ring-1 ring-[#2f8fbf] disabled:opacity-40"
                >
                  ⑂ Fork & run branch
                </button>
                {fork.error && <p className="text-xs text-danger">{fork.error.message}</p>}
              </section>
              {branches.length > 1 && (
                <section className="panel space-y-2 p-3">
                  <h3 className="panel-title text-sm text-gold">Compare branches</h3>
                  <button
                    type="button"
                    onClick={() => setCmp([branches[0]!.head, branches[branches.length - 1]!.head])}
                    className="chip w-full cursor-pointer justify-center py-2 hover:text-text"
                  >
                    {branches[0]!.label} ⇄ {branches[branches.length - 1]!.label}
                  </button>
                </section>
              )}
            </aside>
          </div>
          {compare.data && (
            <section className="panel overflow-x-auto p-3">
              <h3 className="panel-title mb-2 text-sm text-gold">
                Branch comparison (fork point {compare.data.fork_point?.slice(-8)})
              </h3>
              <table className="w-full text-left text-xs">
                <thead className="text-faint">
                  <tr>
                    <th className="py-1 pr-3" />
                    <th className="py-1 pr-3">{branches[0]?.label}</th>
                    <th className="py-1">{branches[branches.length - 1]?.label}</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      "outcome",
                      "steps",
                      "winner",
                      "confidence",
                      "risk",
                      "execution",
                      "verification",
                      "plan_revision",
                    ] as const
                  ).map((k) => (
                    <tr key={k} className="border-t border-border/30">
                      <td className="py-1.5 pr-3 text-faint">{k}</td>
                      <td className="py-1.5 pr-3">{String(compare.data.a[k] ?? "—")}</td>
                      <td className="py-1.5">{String(compare.data.b[k] ?? "—")}</td>
                    </tr>
                  ))}
                  <tr className="border-t border-border/30">
                    <td className="py-1.5 pr-3 text-faint">duration</td>
                    <td>{seconds(compare.data.a.started, compare.data.a.finished)}</td>
                    <td>{seconds(compare.data.b.started, compare.data.b.finished)}</td>
                  </tr>
                  <tr className="border-t border-border/30 align-top">
                    <td className="py-1.5 pr-3 text-faint">answer</td>
                    <td className="py-1.5 pr-3 whitespace-pre-wrap">{compare.data.a.answer.slice(0, 600)}</td>
                    <td className="py-1.5 whitespace-pre-wrap">{compare.data.b.answer.slice(0, 600)}</td>
                  </tr>
                </tbody>
              </table>
            </section>
          )}
        </div>
      )}
    </>
  );
}

export default function Page({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = use(params);
  return (
    <Suspense>
      <TimeTravel missionId={missionId} />
    </Suspense>
  );
}
