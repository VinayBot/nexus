"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "@/components/ui/PageHeader";
import { get } from "@/lib/api";
import { AXIS, GRID, SERIES, TOOLTIP } from "@/lib/chartTheme";
import { cn } from "@/lib/cn";

interface Summary {
  missions: {
    id: string;
    title: string;
    playbook: string | null;
    status: string;
    outcome: string | null;
    duration_s: number;
    prompt: number;
    completion: number;
    calls: number;
    llm_ms: number;
    cloud_cost_usd: number;
  }[];
  event_counts: Record<string, number>;
  by_purpose: Record<string, { calls: number; tokens: number; avg_ms: number }>;
  retries: Record<string, number>;
  routing: { purpose: string; role: string; model: string; reason: string }[];
  circuits: { key: string; state: string; failures: number }[];
  governor: { ts: number; ram_percent: number; tokens_per_sec: number; in_flight: number; queue_depth: number }[];
  cloud_price: { input: number; output: number };
}
interface Span {
  span_id: string;
  parent_id: string | null;
  name: string;
  kind: string;
  start: number;
  end: number;
  status: string;
  attributes: Record<string, unknown>;
}
interface LogRow {
  ts: number;
  level: string;
  logger: string;
  event: string;
  fields: Record<string, string>;
}

const KIND_COLOR: Record<string, string> = { mission: SERIES[1], node: SERIES[0], llm: SERIES[2], tool: SERIES[3] };

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="panel px-4 py-3">
      <p className="text-[11px] text-faint">{label}</p>
      <p className="font-display text-2xl text-text">{value}</p>
      {hint && <p className="text-[10.5px] text-faint">{hint}</p>}
    </div>
  );
}

function Waterfall({ spans }: { spans: Span[] }) {
  if (!spans.length)
    return (
      <p className="text-xs text-faint">
        No spans for this mission (traces are recorded for missions run since tracing was enabled).
      </p>
    );
  const t0 = Math.min(...spans.map((s) => s.start));
  const t1 = Math.max(...spans.map((s) => s.end));
  const total = Math.max(0.001, t1 - t0);
  const depth: Record<string, number> = {};
  const byId = Object.fromEntries(spans.map((s) => [s.span_id, s]));
  const d = (s: Span): number =>
    (depth[s.span_id] ??= s.parent_id && byId[s.parent_id] ? d(byId[s.parent_id]!) + 1 : 0);
  const shown = spans.filter((s) => s.kind !== "tool" || spans.length < 400).slice(0, 220);
  return (
    <div className="max-h-[420px] overflow-y-auto">
      {shown.map((s) => (
        <div
          key={s.span_id}
          className="group flex items-center gap-2 py-px text-[10.5px]"
          title={`${s.name} · ${((s.end - s.start) * 1000).toFixed(0)} ms`}
        >
          <span className="w-44 shrink-0 truncate font-mono text-muted" style={{ paddingLeft: d(s) * 8 }}>
            {s.name}
          </span>
          <div className="relative h-3 flex-1 rounded bg-white/[0.03]">
            <div
              className="absolute h-full rounded-[4px] group-hover:brightness-125"
              style={{
                left: `${((s.start - t0) / total) * 100}%`,
                width: `${Math.max(0.3, ((s.end - s.start) / total) * 100)}%`,
                background: s.status === "error" ? "var(--error)" : (KIND_COLOR[s.kind] ?? SERIES[0]),
              }}
            />
          </div>
          <span className="w-14 shrink-0 text-right font-mono text-faint">
            {((s.end - s.start) * 1000).toFixed(0)}ms
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Page() {
  const summary = useQuery({
    queryKey: ["obs-summary"],
    queryFn: () => get<Summary>("/observability/summary?limit=25"),
    refetchInterval: 15_000,
  });
  const [mission, setMission] = useState<string | null>(null);
  const selected = mission ?? summary.data?.missions[0]?.id ?? null;
  const spans = useQuery({
    queryKey: ["spans", selected],
    queryFn: () => get<Span[]>(`/observability/traces?mission_id=${selected}`),
    enabled: Boolean(selected),
  });
  const [level, setLevel] = useState<string>("");
  const [contains, setContains] = useState("");
  const logs = useQuery({
    queryKey: ["logs", level, contains],
    queryFn: () =>
      get<LogRow[]>(
        `/observability/logs?limit=150${level ? `&level=${level}` : ""}${contains ? `&contains=${encodeURIComponent(contains)}` : ""}`,
      ),
    refetchInterval: 5000,
  });

  const s = summary.data;
  const calls = s?.missions.reduce((a, m) => a + m.calls, 0) ?? 0;
  const tokens = s?.missions.reduce((a, m) => a + m.prompt + m.completion, 0) ?? 0;
  const cost = s?.missions.reduce((a, m) => a + m.cloud_cost_usd, 0) ?? 0;
  const retries = Object.values(s?.retries ?? {}).reduce((a, b) => a + b, 0);
  const purposes = Object.entries(s?.by_purpose ?? {})
    .map(([k, v]) => ({ purpose: k, tokens: v.tokens, avg_ms: v.avg_ms, calls: v.calls }))
    .sort((a, b) => b.tokens - a.tokens);
  const gov = (s?.governor ?? []).map((g) => ({
    t: new Date(g.ts * 1000).toLocaleTimeString(),
    ram: g.ram_percent,
    tps: g.tokens_per_sec,
    queue: g.queue_depth,
  }));

  return (
    <>
      <PageHeader
        title="Observatory"
        kanji="観測"
        description="OpenTelemetry traces, token usage, latency, retries, circuit breakers, routing decisions and the Resource Governor — everything measured, nothing estimated except the clearly labelled cloud-cost comparison."
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Recent missions" value={String(s?.missions.length ?? "—")} />
        <Stat label="LLM calls" value={calls.toLocaleString()} />
        <Stat label="Tokens (local)" value={tokens.toLocaleString()} hint="cost on this laptop: $0" />
        <Stat
          label="Cloud-equivalent"
          value={`$${cost.toFixed(2)}`}
          hint={`at $${s?.cloud_price.input}/$${s?.cloud_price.output} per 1M in/out (illustrative)`}
        />
        <Stat
          label="Retries absorbed"
          value={String(retries)}
          hint={Object.entries(s?.retries ?? {})
            .map(([k, v]) => `${k} ${v}`)
            .join(" · ")}
        />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel min-w-0 p-3">
          <h2 className="panel-title text-sm text-gold">Trace waterfall</h2>
          <select
            value={selected ?? ""}
            onChange={(e) => setMission(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-black/40 px-2 py-1.5 text-xs"
            aria-label="Mission"
          >
            {s?.missions.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title.slice(0, 70)} · {m.status}
              </option>
            ))}
          </select>
          <div className="mt-1 mb-2 flex gap-3 text-[10.5px] text-muted">
            {Object.entries(KIND_COLOR).map(([k, c]) => (
              <span key={k} className="flex items-center gap-1">
                <span className="size-2 rounded-sm" style={{ background: c }} />
                {k}
              </span>
            ))}
          </div>
          <Waterfall spans={spans.data ?? []} />
        </section>
        <section className="panel p-3">
          <h2 className="panel-title text-sm text-gold">Tokens by purpose</h2>
          <p className="text-[10.5px] text-faint">
            Routing sends rewrite/grade/summarise to the fast model, plan/solve/judge to the main one.
          </p>
          <div className="mt-2 h-64">
            <ResponsiveContainer>
              <BarChart data={purposes} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid stroke={GRID} horizontal={false} />
                <XAxis type="number" {...AXIS} />
                <YAxis type="category" dataKey="purpose" width={80} {...AXIS} />
                <Tooltip {...TOOLTIP} formatter={(v) => [Number(v).toLocaleString(), "tokens"]} />
                <Bar dataKey="tokens" fill={SERIES[0]} radius={[0, 4, 4, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <section className="panel p-3">
          <h2 className="panel-title text-sm text-gold">Governor · RAM used %</h2>
          <div className="h-40">
            <ResponsiveContainer>
              <LineChart data={gov}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="t" {...AXIS} minTickGap={50} />
                <YAxis domain={[0, 100]} {...AXIS} width={32} />
                <Tooltip {...TOOLTIP} />
                <Line type="monotone" dataKey="ram" name="RAM %" stroke={SERIES[1]} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel p-3">
          <h2 className="panel-title text-sm text-gold">Governor · tokens / second</h2>
          <div className="h-40">
            <ResponsiveContainer>
              <LineChart data={gov}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="t" {...AXIS} minTickGap={50} />
                <YAxis {...AXIS} width={32} />
                <Tooltip {...TOOLTIP} />
                <Line type="monotone" dataKey="tps" name="tokens/s" stroke={SERIES[0]} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <section className="panel min-w-0 p-3 lg:col-span-2">
          <h2 className="panel-title text-sm text-gold">Missions</h2>
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-faint">
              <tr>
                <th className="py-1">Mission</th>
                <th>Status</th>
                <th className="text-right">Calls</th>
                <th className="text-right">Tokens</th>
                <th className="text-right">LLM time</th>
                <th className="text-right">Wall</th>
              </tr>
            </thead>
            <tbody>
              {s?.missions.map((m) => (
                <tr
                  key={m.id}
                  className="cursor-pointer border-t border-border/30 hover:bg-surface-hover"
                  onClick={() => setMission(m.id)}
                >
                  <td className="max-w-xs truncate py-1">{m.title}</td>
                  <td>
                    {m.status}
                    {m.outcome ? ` · ${m.outcome}` : ""}
                  </td>
                  <td className="text-right font-mono">{m.calls}</td>
                  <td className="text-right font-mono">{(m.prompt + m.completion).toLocaleString()}</td>
                  <td className="text-right font-mono">{(m.llm_ms / 1000).toFixed(0)}s</td>
                  <td className="text-right font-mono">{m.duration_s.toFixed(0)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel space-y-3 p-3">
          <div>
            <h2 className="panel-title text-sm text-gold">Circuit breakers</h2>
            {!s?.circuits.length && <p className="text-xs text-faint">No breakers tripped yet.</p>}
            <ul className="mt-1 space-y-1 text-xs">
              {s?.circuits.map((c) => (
                <li key={c.key} className="flex items-center gap-2">
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      c.state === "closed"
                        ? "bg-success"
                        : c.state === "open"
                          ? "animate-alarm bg-danger"
                          : "bg-warning",
                    )}
                  />
                  <span className="font-mono">{c.key}</span>
                  <span className="ml-auto text-faint">
                    {c.state} · {c.failures} failures
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="panel-title text-sm text-gold">Model routing</h2>
            <ul className="mt-1 max-h-44 space-y-0.5 overflow-y-auto text-[11px]">
              {s?.routing.map((r, i) => (
                <li key={i} className="text-muted">
                  <span className="text-text">{r.purpose}</span> → {r.model}{" "}
                  <span className="text-faint">({r.reason})</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="panel mt-3 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="panel-title text-sm text-gold">Logs</h2>
          {["", "info", "warning", "error"].map((l) => (
            <button
              key={l || "all"}
              type="button"
              onClick={() => setLevel(l)}
              className={cn("chip cursor-pointer", level === l && "border-border-strong text-text")}
            >
              {l || "all"}
            </button>
          ))}
          <input
            value={contains}
            onChange={(e) => setContains(e.target.value)}
            placeholder="filter…"
            className="ml-auto rounded-lg border border-border bg-black/40 px-2 py-1 text-xs"
            aria-label="Filter logs"
          />
        </div>
        <div className="mt-2 max-h-72 overflow-y-auto font-mono text-[10.5px]">
          {logs.data
            ?.slice()
            .reverse()
            .map((r, i) => (
              <div key={i} className="flex gap-2 border-b border-border/20 py-0.5">
                <span className="text-faint">{new Date(r.ts * 1000).toLocaleTimeString()}</span>
                <span
                  className={cn(
                    "w-14",
                    r.level === "error" ? "text-danger" : r.level === "warning" ? "text-warning" : "text-muted",
                  )}
                >
                  {r.level}
                </span>
                <span className="text-text">{r.event}</span>
                <span className="truncate text-faint">
                  {Object.entries(r.fields)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" ")}
                </span>
              </div>
            ))}
        </div>
      </section>
    </>
  );
}
