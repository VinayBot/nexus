"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useState } from "react";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAgents, type AgentInfo } from "@/lib/agents";
import { get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initialRobot } from "@/lib/robotMachine";

interface Rep {
  agent_id: string;
  name: string;
  role: string;
  reputation: number;
  missions?: number;
  wins?: number;
  tournaments?: number;
  steps?: number;
  test_pass_rate?: number | null;
  avg_latency_ms?: number;
  retries?: number;
  topics?: Record<string, number>;
}

function FlipCard({ a, onEdit }: { a: AgentInfo; onEdit: () => void }) {
  const [flipped, setFlipped] = useState(false);
  const [hover, setHover] = useState(false);
  const s = (a.stats ?? {}) as Record<string, number | null>;
  return (
    <div className="h-72 [perspective:1000px]">
      <motion.div
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ type: "spring", stiffness: 120, damping: 16 }}
        className="relative h-full w-full [transform-style:preserve-3d]"
      >
        <button
          type="button"
          onClick={() => setFlipped(true)}
          onPointerEnter={() => setHover(true)}
          onPointerLeave={() => setHover(false)}
          className="panel card-lift absolute inset-0 flex flex-col items-center justify-center gap-1 [backface-visibility:hidden]"
          aria-label={`${a.name}: show spec`}
        >
          <Robot
            avatar={a.avatar}
            state={{ ...initialRobot(0), mode: hover ? "waving" : "idle", expression: hover ? "happy" : "normal" }}
            isCommander={a.id === "commander"}
            size={80}
            showBubble={false}
          />
          <span className="font-display text-base">{a.name}</span>
          <span className="text-[11px] text-gold">{a.title}</span>
          <span className="chip mt-1">
            {a.role} · {a.model_role}
          </span>
        </button>
        <div className="panel absolute inset-0 flex flex-col p-3 text-[11px] [backface-visibility:hidden] [transform:rotateY(180deg)]">
          <p className="font-display text-sm text-gold">{a.name}</p>
          <p className="mt-1 line-clamp-3 text-muted">{a.persona}</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-0.5">
            <dt className="text-faint">model</dt>
            <dd>
              {a.model_role} · t={a.temperature}
            </dd>
            <dt className="text-faint">steps / ctx</dt>
            <dd>
              {a.max_steps} · {a.num_ctx}
            </dd>
            <dt className="text-faint">missions</dt>
            <dd>{s.missions ?? 0}</dd>
            <dt className="text-faint">wins</dt>
            <dd>
              {s.wins ?? 0} / {s.tournaments ?? 0}
            </dd>
            <dt className="text-faint">test pass</dt>
            <dd>{s.test_pass_rate != null ? `${Math.round(Number(s.test_pass_rate) * 100)}%` : "—"}</dd>
            <dt className="text-faint">avg step</dt>
            <dd>{s.avg_latency_ms ? `${(Number(s.avg_latency_ms) / 1000).toFixed(1)}s` : "—"}</dd>
          </dl>
          <p className="mt-2 text-faint">tools</p>
          <div className="flex flex-wrap gap-1 overflow-hidden">
            {a.tools.length ? (
              a.tools.map((t) => (
                <span key={t} className="chip text-[10px]">
                  {t}
                </span>
              ))
            ) : (
              <span className="text-faint">none</span>
            )}
          </div>
          <div className="mt-auto flex gap-2 pt-2">
            <button type="button" onClick={() => setFlipped(false)} className="chip cursor-pointer">
              Back
            </button>
            <button type="button" onClick={onEdit} className="chip cursor-pointer hover:text-text">
              Edit
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function yamlOf(a: Partial<AgentInfo>): string {
  const lines = [
    `id: ${a.id}`,
    `name: ${a.name}`,
    `title: ${a.title}`,
    `role: ${a.role}`,
    `persona: ${a.persona}`,
    "system_prompt: |",
    ...(a.system_prompt ?? "").split("\n").map((l) => `  ${l}`),
    `model_role: ${a.model_role}`,
    `temperature: ${a.temperature}`,
    `tools: [${(a.tools ?? []).join(", ")}]`,
    `max_steps: ${a.max_steps}`,
  ];
  return lines.join("\n");
}

function Editor({ agent, allTools, onClose }: { agent: AgentInfo; allTools: string[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [a, setA] = useState<AgentInfo>(agent);
  const save = useMutation({
    mutationFn: () => {
      const { stats: _stats, builtin: _builtin, ...spec } = a;
      return put(`/agents/${a.id}`, spec as never);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agents"] });
      onClose();
    },
  });
  const field = "w-full rounded-lg border border-border bg-black/40 px-2 py-1.5 text-xs";
  return (
    <section className="panel p-4" aria-label="Edit agent">
      <h2 className="panel-title text-base text-gold">{agent.builtin ? `Edit ${agent.name}` : "New agent"}</h2>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-[11px] text-faint">
            id
            <input
              className={field}
              value={a.id}
              onChange={(e) => setA({ ...a, id: e.target.value })}
              disabled={agent.builtin}
            />
          </label>
          <label className="block text-[11px] text-faint">
            name
            <input className={field} value={a.name} onChange={(e) => setA({ ...a, name: e.target.value })} />
          </label>
          <label className="block text-[11px] text-faint">
            role
            <input className={field} value={a.role} onChange={(e) => setA({ ...a, role: e.target.value })} />
          </label>
          <label className="block text-[11px] text-faint">
            persona
            <input className={field} value={a.persona} onChange={(e) => setA({ ...a, persona: e.target.value })} />
          </label>
          <label className="block text-[11px] text-faint">
            system prompt
            <textarea
              rows={4}
              className={field}
              value={a.system_prompt}
              onChange={(e) => setA({ ...a, system_prompt: e.target.value })}
            />
          </label>
          <div className="flex gap-2">
            <label className="flex-1 text-[11px] text-faint">
              model
              <select
                className={field}
                value={a.model_role}
                onChange={(e) => setA({ ...a, model_role: e.target.value as "main" | "fast" })}
              >
                <option>main</option>
                <option>fast</option>
              </select>
            </label>
            <label className="flex-1 text-[11px] text-faint">
              temperature
              <input
                type="number"
                step={0.05}
                min={0}
                max={1.5}
                className={field}
                value={a.temperature}
                onChange={(e) => setA({ ...a, temperature: Number(e.target.value) })}
              />
            </label>
            <label className="flex-1 text-[11px] text-faint">
              max steps
              <input
                type="number"
                min={1}
                max={12}
                className={field}
                value={a.max_steps}
                onChange={(e) => setA({ ...a, max_steps: Number(e.target.value) })}
              />
            </label>
          </div>
          <fieldset>
            <legend className="text-[11px] text-faint">tool allowlist (MCP)</legend>
            <div className="mt-1 flex flex-wrap gap-1">
              {allTools.map((t) => {
                const on = a.tools.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setA({ ...a, tools: on ? a.tools.filter((x) => x !== t) : [...a.tools, t] })}
                    className={cn("chip cursor-pointer text-[10px]", on && "border-accent text-accent")}
                    aria-pressed={on}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </div>
        <div>
          <p className="text-[11px] text-faint">YAML (saved to data/agents/{a.id}.yaml)</p>
          <pre className="mt-1 max-h-80 overflow-auto rounded-lg bg-black/50 p-2 font-mono text-[10.5px] text-muted">
            {yamlOf(a)}
          </pre>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={() => save.mutate()} disabled={save.isPending} className="btn btn-success">
          Save
        </button>
        <button type="button" onClick={onClose} className="chip cursor-pointer">
          Cancel
        </button>
        {save.error && <span className="text-xs text-danger">{save.error.message}</span>}
      </div>
    </section>
  );
}

export default function Page() {
  const agents = useAgents();
  const rep = useQuery({ queryKey: ["reputation"], queryFn: () => get<Rep[]>("/reputation") });
  const tools = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => get<{ tools: { qualified: string }[]; system_only: boolean }[]>("/mcp/servers"),
  });
  const [editing, setEditing] = useState<AgentInfo | null>(null);
  const [who, setWho] = useState("echo");
  const [msg, setMsg] = useState("Search the knowledge base: what does the Resource Governor do?");
  const play = useMutation({
    mutationFn: () =>
      post<{ answer: string; iterations: number; sources: string[]; latency_ms: number }>(`/agents/${who}/playground`, {
        message: msg,
      }),
  });
  const allTools = (tools.data ?? []).filter((s) => !s.system_only).flatMap((s) => s.tools.map((t) => t.qualified));

  return (
    <>
      <RobotDefs />
      <PageHeader
        title="Agents"
        description="The Agent Registry. Every robot is a YAML spec (persona, prompt, model role, temperature, MCP tool allowlist). Reputation from missions and tournaments guides how the Commander assembles teams."
        actions={
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() =>
              setEditing({
                id: "new_agent",
                name: "New Agent",
                title: "Specialist",
                role: "researcher",
                persona: "Focused specialist.",
                system_prompt: "You are a focused specialist.",
                model_role: "main",
                temperature: 0.2,
                tools: ["knowledge.search"],
                max_steps: 5,
                num_ctx: 4096,
                strategy: null,
                avatar: { color: "#E8ECF2", accent: "#9D7BFF", prop: "tablet" },
                risk_level: "low",
                builtin: false,
                stats: null,
              })
            }
          >
            + New agent
          </button>
        }
      />
      {editing && <Editor agent={editing} allTools={allTools} onClose={() => setEditing(null)} />}
      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="stagger grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-5" data-tour="agents">
          {agents.data?.map((a) => (
            <FlipCard key={a.id} a={a} onEdit={() => setEditing(a)} />
          ))}
        </div>
        <aside className="space-y-3">
          <section className="panel p-3">
            <h2 className="panel-title text-sm text-gold">Reputation leaderboard</h2>
            <ol className="mt-2 space-y-1 text-xs">
              {rep.data?.slice(0, 14).map((r, i) => (
                <li key={r.agent_id} className="flex items-center gap-2">
                  <span className={cn("w-5 text-right font-mono", i < 3 ? "text-gold" : "text-faint")}>{i + 1}</span>
                  <span className="flex-1">{r.name}</span>
                  <span className="text-faint">
                    {r.wins ?? 0} wins · {r.missions ?? 0} missions
                  </span>
                  <span className="w-12 text-right font-mono text-accent">{(r.reputation ?? 0).toFixed(1)}</span>
                </li>
              ))}
            </ol>
          </section>
          <section className="panel space-y-2 p-3">
            <h2 className="panel-title text-sm text-gold">Playground</h2>
            <select
              value={who}
              onChange={(e) => setWho(e.target.value)}
              className="w-full rounded-lg border border-border bg-black/40 px-2 py-1.5 text-xs"
            >
              {agents.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} — {a.title}
                </option>
              ))}
            </select>
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-border bg-black/40 px-2 py-1.5 text-xs"
              aria-label="Message"
            />
            <button
              type="button"
              onClick={() => play.mutate()}
              disabled={play.isPending}
              className="btn btn-secondary btn-sm"
            >
              {play.isPending ? "Thinking (real model)…" : "Run one ReAct task"}
            </button>
            {play.data && (
              <div className="rounded-lg bg-black/40 p-2 text-xs">
                <p className="whitespace-pre-wrap">{play.data.answer}</p>
                <p className="mt-1 text-faint">
                  {play.data.iterations} iterations · tools: {play.data.sources.join(", ") || "none"} ·{" "}
                  {(play.data.latency_ms / 1000).toFixed(1)}s
                </p>
              </div>
            )}
            {play.error && <p className="text-xs text-danger">{play.error.message}</p>}
          </section>
        </aside>
      </div>
    </>
  );
}
