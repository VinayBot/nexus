import { describe, expect, it } from "vitest";
import type { NexusEvent } from "../events";
import { emptyView, reduceAll, reduceMission } from "../missionView";
import { initialRobot, nextRobot, settle } from "../robotMachine";

let seq = 0;
function ev<T extends NexusEvent["type"]>(
  type: T,
  payload: Extract<NexusEvent, { type: T }>["payload"],
  extra: Partial<NexusEvent> = {},
): NexusEvent {
  seq += 1;
  return {
    id: `e${seq}`,
    seq,
    mission_id: "m1",
    thread_id: "m1",
    checkpoint_id: null,
    ts: 1000 + seq,
    agent_id: null,
    node: null,
    type,
    payload,
    ...extra,
  } as NexusEvent;
}

describe("reduceMission", () => {
  it("tracks node lifecycle, edges and fan-out", () => {
    const v = reduceAll([
      ev("mission.started", { resumed: false }),
      ev("node.entered", { node: "dispatch", step: null }),
      ev("send.fanout", { source: "dispatch", target: "worker", count: 3, items: ["a", "b", "c"] }),
      ev("node.exited", { node: "dispatch", duration_ms: 4, status: "ok", updated: ["loops"] }),
      ev("edge.taken", { source: "collect", target: "council", label: "decision matters" }),
    ]);
    expect(v.nodes.dispatch).toEqual({ status: "done", visits: 1, lastMs: 4 });
    expect(v.fanouts[0]?.count).toBe(3);
    expect(v.edges[0]).toMatchObject({ source: "collect", target: "council" });
    expect(v.status).toBe("running");
  });

  it("ignores duplicate sequence numbers (reconnect resume)", () => {
    const e = ev("agent.thinking", { agent_id: "echo", text: "hmm", iteration: 1 });
    const once = reduceMission(emptyView("m1"), e);
    expect(reduceMission(once, e)).toBe(once);
  });

  it("builds the council view and resets it for a new tournament", () => {
    let v = reduceAll([
      ev("council.proposal", { solver_id: "blaze", strategy: "Minimal", summary: "fix A", label: null }),
      ev("council.masked", { mapping_hidden: true, labels: ["A", "B"] }),
      ev("council.review", { reviewer: "vex", target_label: "A", score: 7.5, scores: {}, reason: "ok" }),
      ev("sandbox.test_result", {
        target: "blaze",
        passed: 9,
        failed: 0,
        errors: 0,
        ok: true,
        duration_ms: 1,
        backend: "docker",
        summary: "",
      }),
      ev("council.verdict", {
        winner: "blaze",
        winner_label: "A",
        runner_up: null,
        confidence: 0.8,
        dissent: "-",
        final_scores: { blaze: 8 },
        escalate: false,
      }),
    ]);
    expect(v.council.verdict?.winner).toBe("blaze");
    expect(v.council.tests.blaze?.ok).toBe(true);
    v = reduceMission(
      v,
      ev("council.proposal", { solver_id: "volt", strategy: "Root", summary: "fix B", label: null }),
    );
    expect(Object.keys(v.council.proposals)).toEqual(["volt"]);
    expect(v.council.verdict).toBeNull();
  });

  it("pauses on interrupts and resumes on resolution", () => {
    const v = reduceAll([
      ev("interrupt.raised", { kind: "approve_action", approval_id: "a1", summary: "Apply patch", risk_level: "HIGH" }),
    ]);
    expect(v.status).toBe("paused");
    const r = reduceMission(
      v,
      ev("interrupt.resolved", { approval_id: "a1", decision: "approve", by: "owner", channel: "email" }),
    );
    expect(r.status).toBe("running");
    expect(r.interrupt).toBeNull();
  });
});

describe("robot state machine", () => {
  it("animates thinking → tool → retry → success from real events", () => {
    let r = initialRobot(0);
    r = nextRobot(r, ev("agent.token", { agent_id: "forge", text: "Let me ", purpose: "react" }));
    r = nextRobot(r, ev("agent.token", { agent_id: "forge", text: "read the file", purpose: "react" }));
    expect(r.mode).toBe("thinking");
    expect(r.bubble).toBe("Let me read the file");
    r = nextRobot(r, ev("agent.action", { agent_id: "forge", tool: "workspace.read_file", args: {}, iteration: 1 }));
    expect(r).toMatchObject({ mode: "using_tool", tool: "workspace.read_file", expression: "focused" });
    r = nextRobot(
      r,
      ev("retry", {
        layer: "transport",
        key: "model:x",
        attempt: 2,
        max_attempts: 3,
        reason: "timeout",
        agent_id: "forge",
      }),
    );
    expect(r).toMatchObject({ mode: "retrying", attempt: 2, expression: "confused" });
    r = nextRobot(r, ev("agent.final", { agent_id: "forge", answer: "done" }));
    expect(r.mode).toBe("success");
  });

  it("settles celebrations back to idle and long idleness into sleep", () => {
    const happy = { ...initialRobot(0), mode: "success" as const, since: 0, lastActive: 0 };
    expect(settle(happy, 5000).mode).toBe("idle");
    expect(settle(initialRobot(0), 100_000).mode).toBe("sleeping");
  });
});
