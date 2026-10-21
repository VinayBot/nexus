/** The view model every mission screen renders, and its empty starting state. */
import type { EventOf } from "./events";
import type { RobotState } from "./robotMachine";

export type NodeStatus = "idle" | "active" | "done" | "error" | "interrupted";

export interface NodeView {
  status: NodeStatus;
  visits: number;
  lastMs: number | null;
}

export type ThoughtKind =
  | "thought"
  | "action"
  | "observation"
  | "final"
  | "retry"
  | "route"
  | "plan"
  | "handoff"
  | "tool"
  | "memory"
  | "risk"
  | "guardrail"
  | "verdict"
  | "interrupt"
  | "test"
  | "system";

export interface ThoughtItem {
  id: string;
  seq: number;
  ts: number;
  kind: ThoughtKind;
  agent: string | null;
  title: string;
  body?: string;
  ok?: boolean;
}

export interface CouncilView {
  proposals: Record<string, { strategy: string; summary: string; revised: boolean }>;
  labels: string[];
  reviews: EventOf<"council.review">["payload"][];
  rounds: EventOf<"council.round">["payload"][];
  tests: Record<string, EventOf<"sandbox.test_result">["payload"]>;
  verdict: EventOf<"council.verdict">["payload"] | null;
  active: boolean;
}

export interface MissionView {
  missionId: string | null;
  lastSeq: number;
  status: "idle" | "running" | "paused" | "completed" | "failed" | "cancelled";
  outcome: string | null;
  title: string;
  nodes: Record<string, NodeView>;
  currentNode: string | null;
  edges: { source: string; target: string; label: string; ts: number; seq: number }[];
  robots: Record<string, RobotState>;
  thoughts: ThoughtItem[];
  checkpoints: { id: string; step: number; next: string[]; ts: number; seq: number }[];
  council: CouncilView;
  plan: EventOf<"plan.created">["payload"] | null;
  risk: EventOf<"risk.scored">["payload"] | null;
  interrupt: EventOf<"interrupt.raised">["payload"] | null;
  merges: (EventOf<"reducer.merged">["payload"] & { node: string | null; seq: number })[];
  fanouts: { count: number; items: string[]; ts: number; seq: number }[];
  handoffs: { source: string; target: string; reason: string; ts: number; seq: number }[];
  toolCalls: Record<string, { agent: string | null; tool: string; ts: number; done: boolean; ok?: boolean }>;
  memory: { kind: string; detail: string; ts: number; before?: number; after?: number; agent?: string }[];
  llm: { calls: number; prompt: number; completion: number; byAgent: Record<string, number> };
  loops: Record<string, number>;
  error: string | null;
}

export const emptyCouncil = (): CouncilView => ({
  proposals: {},
  labels: [],
  reviews: [],
  rounds: [],
  tests: {},
  verdict: null,
  active: false,
});

export const emptyView = (missionId: string | null = null): MissionView => ({
  missionId,
  lastSeq: 0,
  status: "idle",
  outcome: null,
  title: "",
  nodes: {},
  currentNode: null,
  edges: [],
  robots: {},
  thoughts: [],
  checkpoints: [],
  council: emptyCouncil(),
  plan: null,
  risk: null,
  interrupt: null,
  merges: [],
  fanouts: [],
  handoffs: [],
  toolCalls: {},
  memory: [],
  llm: { calls: 0, prompt: 0, completion: 0, byAgent: {} },
  loops: {},
  error: null,
});
