/**
 * Robot animation state machine. Pure: (previous state, real backend event) → next
 * state. The Mission Floor renders whatever this returns, so every animation is
 * traceable to an event. Timed decay (e.g. success → idle) is applied by `settle`.
 */
import type { NexusEvent } from "./events";

export type RobotMode =
  | "idle"
  | "walking"
  | "receiving_task"
  | "thinking"
  | "using_tool"
  | "handoff"
  | "debating"
  | "testing"
  | "retrying"
  | "waiting_approval"
  | "success"
  | "failed"
  | "sleeping"
  | "alarm"
  | "waving";

export type Expression = "normal" | "happy" | "focused" | "thinking" | "confused" | "error" | "sleepy";

export interface RobotState {
  mode: RobotMode;
  expression: Expression;
  /** Text in the thought/speech bubble (streamed tokens or a short status). */
  bubble: string;
  /** Retry attempt counter shown on the badge while retrying. */
  attempt: number;
  tool: string | null;
  since: number;
  /** Timestamp of the last event that touched this robot (for sleeping). */
  lastActive: number;
}

export const initialRobot = (now = 0): RobotState => ({
  mode: "idle",
  expression: "normal",
  bubble: "",
  attempt: 0,
  tool: null,
  since: now,
  lastActive: now,
});

const EXPRESSION: Record<RobotMode, Expression> = {
  idle: "normal",
  walking: "normal",
  receiving_task: "focused",
  thinking: "thinking",
  using_tool: "focused",
  handoff: "happy",
  debating: "focused",
  testing: "focused",
  retrying: "confused",
  waiting_approval: "normal",
  success: "happy",
  failed: "error",
  sleeping: "sleepy",
  alarm: "error",
  waving: "happy",
};

/** Map backend `agent.status` strings onto modes. */
const STATUS_MODE: Record<string, RobotMode> = {
  idle: "idle",
  receiving_task: "receiving_task",
  assigning: "handoff",
  pointing: "handoff",
  thinking: "thinking",
  walking: "walking",
  testing: "testing",
  using_tool: "using_tool",
  waiting_approval: "waiting_approval",
  success: "success",
  failed: "failed",
  confused: "retrying",
  retrying: "retrying",
  watching: "testing",
  writing: "thinking",
  running: "walking",
  alarm: "alarm",
};

function to(prev: RobotState, mode: RobotMode, ts: number, patch: Partial<RobotState> = {}): RobotState {
  return {
    ...prev,
    mode,
    expression: EXPRESSION[mode],
    since: mode === prev.mode ? prev.since : ts,
    lastActive: ts,
    ...patch,
  };
}

const tail = (s: string, n = 140) => (s.length > n ? "…" + s.slice(-n) : s);

/** The agent an event animates, if any. */
export function robotFor(e: NexusEvent): string | null {
  switch (e.type) {
    case "agent.status":
    case "agent.thinking":
    case "agent.token":
    case "agent.action":
    case "agent.observation":
    case "agent.final":
    case "agent.assigned":
      return e.payload.agent_id;
    case "council.proposal":
      return e.payload.solver_id === "fix_library" ? null : e.payload.solver_id;
    case "council.review":
      return e.payload.reviewer;
    case "handoff":
      return e.payload.target;
    case "sandbox.test_result":
      return e.payload.target === "fix_library" ? "aegis" : e.payload.target;
    case "retry":
      return e.payload.agent_id ?? e.agent_id ?? null;
    case "tool.called":
    case "tool.result":
    case "council.verdict":
    case "memory.pruned":
    case "memory.summarised":
      return e.agent_id ?? null;
    default:
      return null;
  }
}

export function nextRobot(prev: RobotState, e: NexusEvent): RobotState {
  const ts = e.ts * 1000;
  switch (e.type) {
    case "agent.status":
      return to(prev, STATUS_MODE[e.payload.status] ?? "idle", ts, { bubble: "", attempt: 0 });
    case "agent.assigned":
    case "handoff":
      return to(prev, "receiving_task", ts, { bubble: e.type === "handoff" ? e.payload.reason : e.payload.task });
    case "agent.token":
      return to(prev, "thinking", ts, {
        bubble: tail((prev.mode === "thinking" ? prev.bubble : "") + e.payload.text),
      });
    case "agent.thinking":
      return to(prev, "thinking", ts, { bubble: tail(e.payload.text), attempt: 0 });
    case "agent.action":
    case "tool.called":
      return to(prev, "using_tool", ts, {
        tool: e.type === "agent.action" ? e.payload.tool : `${e.payload.server}.${e.payload.tool}`,
      });
    case "agent.observation":
    case "tool.result":
      return to(prev, "thinking", ts, { tool: null, expression: e.payload.ok ? "thinking" : "confused" });
    case "agent.final":
      return to(prev, "success", ts, { bubble: tail(e.payload.answer, 90), tool: null });
    case "council.proposal":
      return to(prev, "debating", ts, { bubble: tail(e.payload.summary, 90) });
    case "council.review":
      return to(prev, "debating", ts, { bubble: `${e.payload.target_label}: ${e.payload.score.toFixed(1)}` });
    case "council.verdict":
      return to(prev, "success", ts, { bubble: `${e.payload.winner_label} wins` });
    case "sandbox.test_result":
      return to(prev, e.payload.ok ? "success" : "testing", ts, {
        bubble: `${e.payload.passed}✓ ${e.payload.failed + e.payload.errors}✗`,
        expression: e.payload.ok ? "happy" : "error",
      });
    case "retry":
      return to(prev, "retrying", ts, { attempt: e.payload.attempt, bubble: e.payload.layer });
    case "memory.pruned":
    case "memory.summarised":
      return to(prev, "thinking", ts, { bubble: "folding old memories…" });
    default:
      return prev;
  }
}

/** Time-based decay: celebrations and alarms end, long idleness becomes sleep. */
export function settle(s: RobotState, now: number): RobotState {
  const age = now - s.since;
  if ((s.mode === "success" || s.mode === "failed" || s.mode === "handoff") && age > 4000) {
    return { ...s, mode: "idle", expression: "normal", since: now };
  }
  if (s.mode === "retrying" && age > 6000) return { ...s, mode: "idle", expression: "normal", since: now };
  if (s.mode === "idle" && now - s.lastActive > 90_000)
    return { ...s, mode: "sleeping", expression: "sleepy", since: now };
  return s;
}
