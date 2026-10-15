"use client";

import "@xyflow/react/dist/style.css";
import {
  Background,
  BaseEdge,
  Handle,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";
import { memo, useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMissions } from "@/lib/queries";

type Component = {
  id: string;
  label: string;
  x: number;
  y: number;
  tech: string;
  what: string;
  eli: string;
  code: string;
  status?: "backend" | "ollama" | "mcp" | "sqlite" | "demo";
  [key: string]: unknown;
};

const COMPONENTS: Component[] = [
  {
    id: "ui",
    label: "Dojo UI",
    x: 0,
    y: 160,
    tech: "Next.js 15 · React Flow · motion",
    what: "Renders missions as robots, graphs and scrolls. Every live animation is driven by a backend event received over WebSocket.",
    eli: "The screen you are looking at. It never pretends — robots only move when the backend says something happened.",
    code: "frontend/src/",
  },
  {
    id: "api",
    label: "FastAPI",
    x: 220,
    y: 160,
    tech: "REST /api/v1 + WebSockets",
    what: "Creates missions, decides approvals, serves graph structure, history, metrics; streams events with resume-from-seq.",
    eli: "The front desk: the UI asks it for things and listens to it for news.",
    code: "backend/nexus/api/",
    status: "backend",
  },
  {
    id: "runner",
    label: "Mission Runner",
    x: 440,
    y: 160,
    tech: "asyncio tasks · crash recovery",
    what: "Drives the compiled graph per mission (thread), records interrupts as approvals, resumes unfinished missions on restart.",
    eli: "The stage manager: starts each mission, pauses it for humans, and picks it back up after a crash.",
    code: "backend/nexus/graph/runner.py",
  },
  {
    id: "graph",
    label: "LangGraph orchestrator",
    x: 660,
    y: 160,
    tech: "StateGraph · Send · Command · interrupt · RetryPolicy",
    what: "20 nodes: intake → rewrite → route → plan → assemble → dispatch ⇉ workers → council → validate → risk gate → approval → execute → verify → memory → report.",
    eli: "The playbook of the dojo — a flowchart the robots follow, with loops and decision points.",
    code: "backend/nexus/graph/main_graph.py",
  },
  {
    id: "subgraphs",
    label: "Subgraphs",
    x: 660,
    y: 20,
    tech: "ReAct worker · Council/Tournament",
    what: "Workers loop Thought→Action→Observation; the tournament runs parallel solvers, sandbox grounding, anonymous review, debate and an evidence-weighted judge.",
    eli: "Mini-flowcharts inside the big one: how one robot thinks, and how the samurai duel over the best answer.",
    code: "backend/nexus/graph/subgraphs/",
  },
  {
    id: "gateway",
    label: "LLM gateway",
    x: 880,
    y: 160,
    tech: "router · governor · retries · breakers · fallback",
    what: "Every model call: pick fast/main model, take a Resource Governor slot, retry transport errors, validate structured output, fall back, stream tokens.",
    eli: "The careful translator between robots and the AI model — it retries, double-checks answers and never overloads the laptop.",
    code: "backend/nexus/llm/gateway.py",
  },
  {
    id: "ollama",
    label: "Ollama (local)",
    x: 1100,
    y: 160,
    tech: "llama3.2:3b · nomic-embed-text",
    what: "Runs the open models natively on Apple Silicon (Metal). No cloud APIs anywhere.",
    eli: "The brain — running on this laptop, not in the cloud.",
    code: "scripts/ollama_env.sh",
    status: "ollama",
  },
  {
    id: "hub",
    label: "MCP hub",
    x: 660,
    y: 320,
    tech: "mcp 2.x Client · allowlists",
    what: "Seven MCP servers reached through real MCP clients; per-agent allowlists, path jail, system-only email, call log.",
    eli: "The armory: the only way robots can touch files, tests, tickets or email — and each robot may only use certain weapons.",
    code: "backend/nexus/mcp_servers/hub.py",
    status: "mcp",
  },
  {
    id: "sandbox",
    label: "Sandbox",
    x: 440,
    y: 460,
    tech: "Docker (no network, 1 CPU, 512 MB) / local fallback",
    what: "Runs pytest on a throwaway copy of the workspace so patches are proven before anyone sees them.",
    eli: "A sealed practice room where fixes are tested without touching the real service.",
    code: "backend/nexus/mcp_servers/sandbox_runner.py",
  },
  {
    id: "chroma",
    label: "ChromaDB",
    x: 660,
    y: 460,
    tech: "embedded · PCA map",
    what: "Long-term memory: Fix Library, past missions, docs, lessons. Only the backend process opens it.",
    eli: "The library where the clan remembers past incidents and fixes.",
    code: "backend/nexus/memory/long_term.py",
  },
  {
    id: "demo",
    label: "demo-service",
    x: 880,
    y: 460,
    tech: "FastAPI · uvicorn --reload · git",
    what: "The orders service being watched. Chaos switches inject real bugs; fixes land on a branch and hot-reload.",
    eli: "The patient: a small shop app that the clan keeps healthy.",
    code: "demo-service/",
    status: "demo",
  },
  {
    id: "sqlite",
    label: "SQLite",
    x: 440,
    y: 320,
    tech: "checkpoints · events · approvals · audit · traces",
    what: "Checkpoints every super-step (time travel, resume), persists events (replay), approvals, audit log and OTel spans.",
    eli: "The diary: everything that happened, step by step, so we can rewind.",
    code: "backend/nexus/db/",
    status: "sqlite",
  },
  {
    id: "bus",
    label: "Event bus",
    x: 220,
    y: 320,
    tech: "typed Pydantic events → WS",
    what: "Nodes, agents and tools emit typed events; the bus fans them out to WebSockets and batches them into SQLite.",
    eli: "The town crier: shouts every step so the UI can animate it.",
    code: "backend/nexus/core/events.py",
  },
  {
    id: "mail",
    label: "Mailpit",
    x: 1100,
    y: 320,
    tech: "SMTP capture · signed links",
    what: "Approval emails with signed, single-use links (GET confirm page, POST decides).",
    eli: "Where the owner gets the 'may we apply this fix?' letter.",
    code: "backend/nexus/hitl/email_approvals.py",
  },
];

const LINKS: [string, string, boolean][] = [
  ["ui", "api", true],
  ["api", "runner", true],
  ["runner", "graph", true],
  ["graph", "gateway", true],
  ["gateway", "ollama", true],
  ["graph", "subgraphs", true],
  ["graph", "hub", true],
  ["hub", "sandbox", true],
  ["hub", "chroma", false],
  ["hub", "demo", false],
  ["hub", "mail", false],
  ["runner", "sqlite", true],
  ["graph", "bus", true],
  ["bus", "api", true],
  ["bus", "sqlite", false],
];

type CData = Component & { ok: boolean | null; selected: boolean; eliMode: boolean };

const Box = memo(function Box({ data }: NodeProps<Node<CData>>) {
  return (
    <div
      className={cn(
        "w-48 rounded-xl border bg-[color-mix(in_srgb,var(--lacquer)_92%,transparent)] px-3 py-2",
        data.selected ? "border-accent shadow-[var(--glow-cyan)]" : "border-border-strong",
      )}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <Handle type="target" id="t" position={Position.Top} className="!opacity-0" />
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-text">{data.label}</span>
        {data.ok !== null && (
          <span className={cn("ml-auto size-2 rounded-full", data.ok ? "bg-success" : "animate-alarm bg-danger")} />
        )}
      </div>
      <p className="text-[10px] text-faint">{data.tech}</p>
      <Handle type="source" position={Position.Right} className="!opacity-0" />
      <Handle type="source" id="b" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
});

const Packet = memo(function Packet(props: EdgeProps<Edge<{ hot: boolean }>>) {
  const [path] = getSmoothStepPath(props);
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        style={{
          stroke: props.data?.hot ? "var(--cyan)" : "rgba(247,164,64,0.4)",
          strokeWidth: props.data?.hot ? 1.8 : 1.2,
        }}
      />
      {props.data?.hot && (
        <circle r={3.5} fill="var(--sun-core)" style={{ filter: "drop-shadow(0 0 4px var(--sun-gold))" }}>
          <animateMotion dur="1.6s" repeatCount="indefinite" path={path} />
        </circle>
      )}
    </>
  );
});

const nodeTypes = { box: Box };
const edgeTypes = { packet: Packet };

export default function Page() {
  const [selected, setSelected] = useState("graph");
  const [eli, setEli] = useState(false);
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: () => get<{ status: string; checks: { name: string; status: string }[] }>("/health/ready"),
    refetchInterval: 10_000,
  });
  const mcp = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => get<{ health: { status: string } | null }[]>("/mcp/servers"),
    refetchInterval: 15_000,
  });
  const chaos = useQuery({
    queryKey: ["chaos"],
    queryFn: () => get<{ health: { status: string } }>("/chaos"),
    refetchInterval: 10_000,
  });
  const missions = useMissions(10);
  const running = missions.data?.some((m) => m.status === "running") ?? false;

  const status = useMemo(() => {
    const check = (n: string) => ready.data?.checks.find((c) => c.name === n)?.status;
    return {
      backend: ready.data ? true : ready.isError ? false : null,
      ollama: check("ollama") ? check("ollama") !== "down" : null,
      sqlite: check("sqlite") ? check("sqlite") === "ok" : null,
      mcp: mcp.data ? mcp.data.every((s) => s.health?.status === "ok") : null,
      demo: chaos.data ? chaos.data.health.status !== "down" : null,
    } as Record<string, boolean | null>;
  }, [ready.data, ready.isError, mcp.data, chaos.data]);

  const nodes: Node<CData>[] = COMPONENTS.map((c) => ({
    id: c.id,
    type: "box",
    position: { x: c.x, y: c.y },
    data: { ...c, ok: c.status ? (status[c.status] ?? null) : null, selected: selected === c.id, eliMode: eli },
  }));
  const edges: Edge<{ hot: boolean }>[] = LINKS.map(([a, b, main]) => ({
    id: `${a}-${b}`,
    source: a,
    target: b,
    type: "packet",
    data: { hot: running && main },
  }));
  const sel = COMPONENTS.find((c) => c.id === selected)!;

  return (
    <>
      <PageHeader
        title="Architecture Explorer"
        kanji="設計"
        description={
          running
            ? "A mission is running — light packets trace the real request path."
            : "Click any component. Packets flow along the request path while a mission runs."
        }
        actions={
          <label className="chip cursor-pointer gap-2">
            <input type="checkbox" checked={eli} onChange={(e) => setEli(e.target.checked)} /> Explain like I&apos;m new
          </label>
        }
      />
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="panel h-[600px] overflow-hidden" data-tour="architecture">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.08 }}
            onNodeClick={(_, n) => setSelected(n.id)}
            proOptions={{ hideAttribution: true }}
            colorMode="dark"
            nodesConnectable={false}
          >
            <Background color="rgba(247,164,64,0.1)" gap={28} />
          </ReactFlow>
        </div>
        <aside className="panel p-4">
          <h2 className="font-display text-xl text-gold">{sel.label}</h2>
          <p className="text-[11px] text-faint">{sel.tech}</p>
          <p className="mt-3 text-sm leading-relaxed text-text">{eli ? sel.eli : sel.what}</p>
          <p className="mt-3 text-[11px] text-faint">Code</p>
          <p className="font-mono text-xs text-accent">{sel.code}</p>
          {sel.status && (
            <p className="mt-3 text-xs">
              Live status:{" "}
              <span
                className={
                  status[sel.status] ? "text-success" : status[sel.status] === false ? "text-danger" : "text-faint"
                }
              >
                {status[sel.status] === null ? "checking…" : status[sel.status] ? "healthy" : "unhealthy"}
              </span>
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
