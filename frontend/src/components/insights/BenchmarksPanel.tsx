"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PanelIntro } from "@/components/ui/PageHeader";
import { get, post } from "@/lib/api";
import { AXIS, GRID, SERIES, TOOLTIP } from "@/lib/chartTheme";
import { cn } from "@/lib/cn";

interface Run {
  id: string;
  suite: string;
  status: string;
  started_at: number;
  finished_at: number | null;
  model: string;
  summary: Record<string, Record<string, number> | string>;
  cases: Record<string, unknown>[];
}

const DESCRIPTIONS: Record<string, string> = {
  raw_vs_langgraph:
    "Three tool-using tasks with known answers, through the framework-free agent and the LangGraph ReAct worker (via MCP).",
  council_vs_single:
    "Four questions with reference keywords: one model call vs a three-solver council with anonymous review and a judge.",
  pruning:
    "A long conversation with three planted facts squeezed into a 420-token budget: tokens saved vs facts still answerable.",
};

/** Grouped bars: one group per metric, one bar per contender (legend + tooltip). */
function SummaryChart({ run }: { run: Run }) {
  const sides = Object.keys(run.summary).filter((k) => typeof run.summary[k] === "object");
  if (!sides.length) return null;
  const metrics = Object.keys(run.summary[sides[0]!] as Record<string, number>);
  const data = metrics.map((m) => ({
    metric: m,
    ...Object.fromEntries(sides.map((s) => [s, (run.summary[s] as Record<string, number>)[m]])),
  }));
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {data.map((row) => (
        <div key={row.metric} className="h-44">
          <p className="text-[11px] text-muted">{row.metric.replace(/_/g, " ")}</p>
          <ResponsiveContainer>
            <BarChart data={[row]} margin={{ top: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="metric" hide />
              <YAxis {...AXIS} width={44} />
              <Tooltip {...TOOLTIP} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#c9b2a3" }} />
              {sides.map((s, i) => (
                <Bar key={s} dataKey={s} fill={SERIES[i % SERIES.length]} radius={[4, 4, 0, 0]} barSize={28} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

export function BenchmarksPanel() {
  const qc = useQueryClient();
  const suites = useQuery({
    queryKey: ["eval-suites"],
    queryFn: () => get<{ id: string; title: string }[]>("/evals/suites"),
  });
  const runs = useQuery({
    queryKey: ["eval-runs"],
    queryFn: () => get<Run[]>("/evals/runs"),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 4000 : false),
  });
  const start = useMutation({
    mutationFn: (suite: string) => post(`/evals/${suite}/run`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["eval-runs"] }),
  });
  const running = runs.data?.some((r) => r.status === "running");

  return (
    <>
      <PanelIntro
        title="Benchmarks"
        description="Benchmarks run live against your local models — honest numbers, including the failures. One suite at a time so the laptop stays responsive."
      />
      <div className="grid gap-3 md:grid-cols-3">
        {suites.data?.map((s) => {
          const last = runs.data?.find((r) => r.suite === s.id);
          return (
            <section key={s.id} className="panel flex flex-col p-3">
              <h2 className="panel-title text-sm text-gold">{s.title}</h2>
              <p className="mt-1 flex-1 text-xs text-muted">{DESCRIPTIONS[s.id]}</p>
              <div className="mt-2 flex items-center gap-2">
                <button
                  type="button"
                  disabled={running || start.isPending}
                  onClick={() => start.mutate(s.id)}
                  className="btn btn-secondary btn-sm"
                >
                  {last?.status === "running" ? "Running…" : "Run suite"}
                </button>
                {last && (
                  <span className="text-[11px] text-faint">
                    last: {last.status} · {new Date(last.started_at * 1000).toLocaleString()}
                  </span>
                )}
              </div>
            </section>
          );
        })}
      </div>
      {start.error && <p className="mt-2 text-xs text-danger">{start.error.message}</p>}
      <div className="mt-3 space-y-3">
        {runs.data
          ?.filter((r) => r.status !== "running")
          .slice(0, 6)
          .map((r) => (
            <section key={r.id} className="panel p-3">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-display text-sm">{suites.data?.find((s) => s.id === r.suite)?.title ?? r.suite}</h3>
                <span className={cn("chip", r.status === "failed" && "text-danger")}>{r.status}</span>
                <span className="text-[11px] text-faint">
                  {r.model} · {r.finished_at ? `${(r.finished_at - r.started_at).toFixed(0)}s` : ""}
                </span>
              </div>
              {typeof r.summary.error === "string" ? (
                <p className="mt-2 text-xs text-danger">{r.summary.error}</p>
              ) : (
                <div className="mt-2">
                  <SummaryChart run={r} />
                </div>
              )}
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px] text-faint">Cases (table view)</summary>
                <pre className="mt-1 max-h-72 overflow-auto rounded bg-black/40 p-2 font-mono text-[10.5px] text-muted">
                  {JSON.stringify(r.cases, null, 2)}
                </pre>
              </details>
            </section>
          ))}
        {runs.data?.length === 0 && <p className="text-sm text-faint">No runs yet.</p>}
      </div>
    </>
  );
}
