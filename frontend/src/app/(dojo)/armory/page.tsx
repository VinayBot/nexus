"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Tool {
  name: string;
  qualified: string;
  description: string;
  input_schema: {
    properties?: Record<string, { type?: string; description?: string; default?: unknown }>;
    required?: string[];
  };
}
interface Server {
  name: string;
  instructions: string;
  system_only: boolean;
  tools: Tool[];
  health: {
    status: string;
    ping_ms: number;
    calls: number;
    errors: number;
    avg_ms: number | null;
    last_error: string | null;
  } | null;
}
interface Call {
  id: string;
  ts: number;
  tool: string;
  agent_id: string | null;
  mission_id: string | null;
  args: Record<string, unknown>;
  ok: boolean;
  result: string;
  duration_ms: number;
}

const WEAPON: Record<string, string> = {
  workspace: "🗡",
  sandbox: "🛡",
  knowledge: "📜",
  tickets: "🏮",
  notify: "✉",
  observability: "🔭",
  demo: "🎯",
};

function defaults(tool: Tool): string {
  const props = tool.input_schema.properties ?? {};
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (k === "workspace" || k === "mission_id") continue;
    out[k] = v.default ?? (v.type === "integer" || v.type === "number" ? 1 : "");
  }
  if (tool.qualified === "knowledge.search") out.query = "reducers";
  if (tool.qualified === "demo.calculator") out.expression = "17 * 23";
  return JSON.stringify(out, null, 2);
}

export default function Page() {
  const servers = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => get<Server[]>("/mcp/servers"),
    refetchInterval: 10_000,
  });
  const sandbox = useQuery({
    queryKey: ["sandbox"],
    queryFn: () => get<{ backend: string; isolated: boolean; reason: string }>("/mcp/sandbox"),
  });
  const [server, setServer] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool | null>(null);
  const [args, setArgs] = useState("{}");
  const calls = useQuery({
    queryKey: ["mcp-calls", server],
    queryFn: () => get<Call[]>(`/mcp/calls?limit=40${server ? `&server=${server}` : ""}`),
    refetchInterval: 5000,
  });
  const tryTool = useMutation({
    mutationFn: () =>
      post<{ ok: boolean; text: string; duration_ms: number }>("/mcp/try", {
        tool: tool!.qualified,
        args: JSON.parse(args),
      }),
  });

  return (
    <>
      <PageHeader
        title="Armory"
        kanji="武器"
        description={
          <>
            NEXUS&apos;s own MCP servers. Agents reach every tool through an MCP client (full protocol), filtered by
            per-agent allowlists; <code>notify</code> is system-only so no email leaves without approval. Sandbox:{" "}
            <span className={sandbox.data?.isolated ? "text-success" : "text-warning"}>
              {sandbox.data?.backend ?? "…"}
            </span>
            {sandbox.data && !sandbox.data.isolated && <span className="text-faint"> — {sandbox.data.reason}</span>}
          </>
        }
      />
      {servers.isError && <EmptyState title="Backend unreachable" tone="error" />}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {servers.data?.map((s) => {
          const ok = s.health?.status === "ok";
          return (
            <motion.button
              key={s.name}
              type="button"
              whileHover={{ y: -3 }}
              onClick={() => setServer(server === s.name ? null : s.name)}
              className={cn("panel p-3 text-left", server === s.name && "border-border-strong")}
            >
              <div className="flex items-center gap-2">
                <span className="text-2xl" aria-hidden>
                  {WEAPON[s.name] ?? "⚔"}
                </span>
                <span className="font-display text-base">{s.name}</span>
                <span
                  className={cn(
                    "ml-auto size-2.5 rounded-full",
                    ok ? "bg-success shadow-[0_0_8px_var(--success)]" : "animate-alarm bg-danger",
                  )}
                  title={s.health?.status}
                />
              </div>
              <p className="mt-1 text-[11px] text-muted">{s.instructions}</p>
              <p className="mt-2 font-mono text-[10.5px] text-faint">
                {s.tools.length} tools · {s.health?.calls ?? 0} calls · {s.health?.errors ?? 0} errors · ping{" "}
                {s.health?.ping_ms ?? "—"} ms
                {s.system_only && <span className="ml-1 text-warning">· system-only</span>}
              </p>
              {/* weapon rack: one blade per tool */}
              <div className="mt-2 flex gap-1.5">
                {s.tools.map((t) => (
                  <span
                    key={t.name}
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      setTool(t);
                      setArgs(defaults(t));
                    }}
                    className={cn(
                      "chip cursor-pointer",
                      tool?.qualified === t.qualified && "border-accent text-accent",
                    )}
                  >
                    {t.name}
                  </span>
                ))}
              </div>
            </motion.button>
          );
        })}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <section className="panel p-3">
          <h2 className="panel-title text-sm text-gold">{tool ? tool.qualified : "Pick a tool"}</h2>
          {tool ? (
            <>
              <p className="mt-1 text-xs text-muted">{tool.description}</p>
              <h3 className="mt-2 text-[10px] tracking-wider text-faint uppercase">Input schema</h3>
              <pre className="max-h-40 overflow-auto rounded bg-black/40 p-2 font-mono text-[10.5px] text-muted">
                {JSON.stringify(tool.input_schema, null, 2)}
              </pre>
              <h3 className="mt-2 text-[10px] tracking-wider text-faint uppercase">Try it (playground workspace)</h3>
              <textarea
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                rows={4}
                className="w-full rounded-lg border border-border bg-black/50 p-2 font-mono text-[11px]"
                aria-label="Arguments JSON"
              />
              <button
                type="button"
                disabled={tryTool.isPending || tool.qualified.startsWith("notify.")}
                onClick={() => tryTool.mutate()}
                className="chip mt-1 cursor-pointer px-3 py-1.5 hover:text-text disabled:opacity-40"
              >
                {tool.qualified.startsWith("notify.")
                  ? "Needs an approved mission"
                  : tryTool.isPending
                    ? "Calling…"
                    : "Call tool"}
              </button>
              {tryTool.data && (
                <pre
                  className={cn(
                    "mt-2 max-h-56 overflow-auto rounded p-2 font-mono text-[10.5px]",
                    tryTool.data.ok ? "bg-success/5 text-text" : "bg-danger/10 text-danger",
                  )}
                >
                  {tryTool.data.text} {"\n"}— {tryTool.data.duration_ms} ms
                </pre>
              )}
              {tryTool.error && <p className="mt-1 text-xs text-danger">{tryTool.error.message}</p>}
            </>
          ) : (
            <p className="mt-2 text-xs text-faint">Click a blade on any rack to inspect its schema and call it.</p>
          )}
        </section>
        <section className="panel min-w-0 p-3">
          <h2 className="panel-title text-sm text-gold">Recent calls {server ? `· ${server}` : ""}</h2>
          <ul className="mt-2 max-h-[420px] space-y-1 overflow-y-auto">
            {calls.data?.map((c) => (
              <li key={c.id} className="rounded border border-border/40 px-2 py-1 text-[11px]">
                <div className="flex gap-2">
                  <span className={c.ok ? "text-success" : "text-danger"}>{c.ok ? "✓" : "✗"}</span>
                  <span className="font-mono text-accent">{c.tool}</span>
                  <span className="text-muted">{c.agent_id ?? "system"}</span>
                  <span className="ml-auto font-mono text-faint">
                    {Math.round(c.duration_ms)} ms · {new Date(c.ts * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <p className="truncate font-mono text-faint" title={JSON.stringify(c.args)}>
                  {JSON.stringify(c.args)}
                </p>
                <p className="line-clamp-2 font-mono text-muted">{c.result}</p>
              </li>
            ))}
            {calls.data?.length === 0 && <li className="text-xs text-faint">No calls yet.</li>}
          </ul>
        </section>
      </div>
    </>
  );
}
