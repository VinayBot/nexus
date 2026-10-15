import { canonicalId } from "@/lib/agentIds";

/** Where each robot stands on the Mission Floor (percent of the floor box). */
export const POSTS: Record<string, { x: number; y: number; z?: number }> = {
  commander: { x: 50, y: 22, z: 3 },
  sage: { x: 30, y: 30 },
  quill: { x: 70, y: 30 },
  echo: { x: 15, y: 60 },
  forge: { x: 31, y: 66 },
  aegis: { x: 47, y: 68 },
  swift: { x: 89, y: 34 },
  hawk: { x: 91, y: 7 },
  arbiter: { x: 74, y: 50 },
  blaze: { x: 63, y: 70 },
  volt: { x: 74, y: 78 },
  frost: { x: 85, y: 70 },
  vex: { x: 93, y: 56 },
};

/** The MCP tools terminal (tool-call beams point here). */
export const TOOLS = { x: 6, y: 86 };
/** Sandbox test light bars. */
export const TEST_BAY = { x: 54, y: 93 };

export function postOf(id: string, index = 0): { x: number; y: number; z?: number } {
  return POSTS[canonicalId(id)] ?? { x: 12 + ((index * 17) % 76), y: 44 };
}

/** Main-graph stages shown in the mini-map strip, in flow order. */
export const STAGES: { id: string; label: string }[] = [
  { id: "intake", label: "Intake" },
  { id: "rewrite", label: "Rewrite" },
  { id: "route", label: "Route" },
  { id: "plan", label: "Plan" },
  { id: "assemble", label: "Team" },
  { id: "dispatch", label: "Dispatch" },
  { id: "worker", label: "Workers" },
  { id: "council", label: "Council" },
  { id: "validate", label: "Validate" },
  { id: "risk_gate", label: "Risk" },
  { id: "approval", label: "Approval" },
  { id: "execute", label: "Execute" },
  { id: "verify", label: "Verify" },
  { id: "memory_write", label: "Memory" },
  { id: "report", label: "Report" },
];
