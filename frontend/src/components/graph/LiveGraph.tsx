"use client";

import "@xyflow/react/dist/style.css";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  getBezierPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { memo, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { MissionView, NodeView } from "@/lib/missionView";
import { StateInspector } from "./StateInspector";
import { positionOf } from "./graphLayout";

export interface GraphStructure {
  nodes: {
    id: string;
    label: string;
    agent: string | null;
    topic: string | null;
    kind: "node" | "terminal" | "interrupt";
    parallel: boolean;
    subgraph: string | null;
  }[];
  edges: { source: string; target: string; conditional: boolean; label: string | null }[];
  subgraphs: Record<
    string,
    { nodes: { id: string; label: string }[]; edges: { source: string; target: string; conditional: boolean }[] }
  >;
  reducers: Record<string, string>;
  limits: Record<string, number>;
}

export const useGraphStructure = () =>
  useQuery({
    queryKey: ["graph-structure"],
    queryFn: () => get<GraphStructure>("/graph/structure"),
    staleTime: Infinity,
  });

type LanternData = {
  label: string;
  agent: string | null;
  kind: string;
  parallel: boolean;
  subgraph: string | null;
  state?: NodeView;
  fanout: number;
};

const LanternNode = memo(function LanternNode({ data }: NodeProps<Node<LanternData>>) {
  const s = data.state?.status ?? "idle";
  const active = s === "active";
  const interrupt = data.kind === "interrupt";
  const terminal = data.kind === "terminal";
  if (terminal) {
    return (
      <div className="grid size-9 place-items-center rounded-full border border-border-strong bg-black/60 text-[10px] text-faint">
        <Handle type="target" id="tl" position={Position.Left} className="!opacity-0" />
        <Handle type="target" id="tr" position={Position.Right} className="!opacity-0" />
        <Handle type="target" id="tt" position={Position.Top} className="!opacity-0" />
        <Handle type="target" id="tb" position={Position.Bottom} className="!opacity-0" />
        {data.label === "start" ? "▶" : "■"}
        <Handle type="source" id="sr" position={Position.Right} className="!opacity-0" />
        <Handle type="source" id="sl" position={Position.Left} className="!opacity-0" />
        <Handle type="source" id="sb" position={Position.Bottom} className="!opacity-0" />
        <Handle type="source" id="st" position={Position.Top} className="!opacity-0" />
      </div>
    );
  }
  return (
    <motion.div
      animate={
        active
          ? {
              boxShadow: interrupt
                ? ["0 0 0px #ff4d4f", "0 0 26px #ff4d4f", "0 0 0px #ff4d4f"]
                : ["0 0 6px #4fe3f0", "0 0 26px #4fe3f0", "0 0 6px #4fe3f0"],
            }
          : { boxShadow: "0 0 0px transparent" }
      }
      transition={active ? { repeat: Infinity, duration: 1.4 } : { duration: 0.3 }}
      className={cn(
        "relative min-w-[136px] rounded-md border px-3 py-2 text-center",
        "bg-[rgb(8_11_20/0.94)]",
        s === "idle" && "border-border opacity-75",
        s === "done" && "border-[rgb(79_227_240/0.45)]",
        active && (interrupt ? "border-danger" : "border-accent"),
        s === "error" && "border-danger",
        s === "interrupted" && "animate-alarm border-danger",
        data.parallel && "outline outline-1 outline-offset-4 outline-accent/30",
      )}
    >
      <Handle type="target" id="tl" position={Position.Left} className="!size-1.5 !border-0 !bg-[var(--cyan)]" />
      <Handle type="target" id="tr" position={Position.Right} className="!opacity-0" />
      <Handle type="target" id="tt" position={Position.Top} className="!opacity-0" />
      <Handle type="target" id="tb" position={Position.Bottom} className="!opacity-0" />
      <div
        className={cn("text-[12px] font-semibold", active ? "text-text" : s === "done" ? "text-gold" : "text-muted")}
      >
        {data.label}
      </div>
      <div className="text-[9.5px] text-faint">
        {data.agent ?? ""}
        {data.subgraph ? ` · subgraph` : ""}
        {data.state?.lastMs != null ? ` · ${Math.round(data.state.lastMs)}ms` : ""}
      </div>
      {(data.state?.visits ?? 0) > 1 && (
        <span
          className="absolute -top-2 -right-2 rounded-full bg-warning px-1.5 font-mono text-[10px] font-bold text-[var(--ink)]"
          title="cycle iterations"
        >
          ×{data.state!.visits}
        </span>
      )}
      {data.parallel && data.fanout > 0 && (
        <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-accent/60 bg-black px-1.5 text-[9.5px] text-accent">
          Send ×{data.fanout}
        </span>
      )}
      <Handle type="source" id="sr" position={Position.Right} className="!size-1.5 !border-0 !bg-[var(--cyan)]" />
      <Handle type="source" id="sl" position={Position.Left} className="!opacity-0" />
      <Handle type="source" id="sb" position={Position.Bottom} className="!opacity-0" />
      <Handle type="source" id="st" position={Position.Top} className="!opacity-0" />
    </motion.div>
  );
});

type FlowData = { label: string | null; hot: number; conditional: boolean; taken: string | null };

/** Edge that carries flowing light particles when it was just taken. */
const FlowEdge = memo(function FlowEdge(props: EdgeProps<Edge<FlowData>>) {
  const [path, lx, ly] = getBezierPath(props);
  const d = props.data;
  const hot = (d?.hot ?? 0) > 0;
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        style={{
          stroke: hot ? "var(--cyan)" : d?.conditional ? "rgba(255,181,71,0.4)" : "rgba(148,163,210,0.45)",
          strokeWidth: hot ? 2.2 : 1.2,
          strokeDasharray: d?.conditional && !hot ? "5 5" : undefined,
          filter: hot ? "drop-shadow(0 0 4px var(--cyan))" : undefined,
        }}
      />
      {hot &&
        Array.from({ length: Math.min(3, d!.hot) }, (_, i) => (
          <circle key={i} r={3} fill="var(--sun-core)" style={{ filter: "drop-shadow(0 0 4px var(--sun-gold))" }}>
            <animateMotion dur="1.4s" repeatCount="indefinite" begin={`${i * 0.45}s`} path={path} />
          </circle>
        ))}
      {(d?.taken || (d?.label && d.conditional)) && (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "pointer-events-none absolute rounded-full border px-1.5 py-px text-[9.5px] whitespace-nowrap",
              d?.taken ? "border-accent bg-black/80 text-accent" : "border-border/50 bg-black/60 text-faint",
            )}
            style={{ transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)` }}
          >
            {d?.taken ?? d?.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

const nodeTypes = { lantern: LanternNode };
const edgeTypes = { flow: FlowEdge };

export function LiveGraph({ view, showInspector = false }: { view: MissionView; showInspector?: boolean }) {
  const { data, isError } = useGraphStructure();
  const [inspector, setInspector] = useState(showInspector);

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    const recent = view.edges.slice(-4);
    const lastFanout = view.fanouts[view.fanouts.length - 1]?.count ?? 0;
    const nodes: Node<LanternData>[] = data.nodes.map((n, i) => ({
      id: n.id,
      type: "lantern",
      position: positionOf(n.id, i),
      data: {
        label: n.label,
        agent: n.agent,
        kind: n.kind,
        parallel: n.parallel,
        subgraph: n.subgraph,
        state: view.nodes[n.id],
        fanout: lastFanout,
      },
      draggable: true,
    }));
    const edges: Edge<FlowData>[] = data.edges.map((e) => {
      const takenIdx = recent.findIndex((r) => r.source === e.source && r.target === e.target);
      const takenAt = takenIdx >= 0 ? recent[takenIdx] : undefined;
      const fanoutHot = e.source === "dispatch" && e.target === "worker" && view.currentNode === "worker";
      const directHot = view.currentNode === e.target && view.nodes[e.source]?.status === "done" && !e.conditional;
      const hot = fanoutHot ? lastFanout : takenAt && takenIdx === recent.length - 1 ? 1 : directHot ? 1 : 0;
      // pick the sides that face each other so the snake's rows connect cleanly
      const a = positionOf(e.source, 0);
      const b = positionOf(e.target, 0);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const [sh, th] =
        Math.abs(dy) > Math.abs(dx) * 0.8
          ? dy > 0
            ? ["sb", "tt"]
            : ["st", "tb"]
          : dx >= 0
            ? ["sr", "tl"]
            : ["sl", "tr"];
      return {
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        sourceHandle: sh,
        targetHandle: th,
        type: "flow",
        data: { label: e.label, hot, conditional: e.conditional, taken: takenAt?.label ?? null },
      };
    });
    return { nodes, edges };
  }, [data, view.nodes, view.edges, view.fanouts, view.currentNode]);

  if (isError)
    return (
      <div className="grid h-full place-items-center text-sm text-danger">Could not load the graph structure.</div>
    );
  return (
    <div className="flex h-full">
      <div className="relative min-w-0 flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.3}
          proOptions={{ hideAttribution: true }}
          colorMode="dark"
          nodesConnectable={false}
        >
          <Background color="rgba(247,164,64,0.12)" gap={28} />
          <Controls showInteractive={false} className="!border-border !bg-black/60" />
        </ReactFlow>
        <div className="pointer-events-none absolute bottom-2 left-12 flex flex-wrap gap-1.5 text-[10px]">
          <span className="chip">— edge · - - conditional</span>
          <span className="chip">×N cycle iterations</span>
          <span className="chip">⦿ parallel Send</span>
        </div>
        <button
          type="button"
          onClick={() => setInspector((x) => !x)}
          className="chip absolute top-2 right-2 cursor-pointer hover:text-text"
        >
          {inspector ? "Hide" : "State"} inspector
        </button>
      </div>
      {inspector && view.missionId && <StateInspector view={view} reducers={data?.reducers ?? {}} />}
    </div>
  );
}
