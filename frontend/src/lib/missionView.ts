/**
 * Folds a mission's event stream into the view model every screen renders.
 * Pure and incremental: `reduceMission(view, event)` — the same function drives
 * Live mode (events arriving over the WebSocket) and Replay mode (persisted
 * events re-fed at any speed), so both look identical.
 */
import { canonicalEvent } from "./agentIds";
import type { NexusEvent } from "./events";
import { initialRobot, nextRobot, robotFor } from "./robotMachine";

export * from "./missionViewTypes";
import { emptyCouncil, emptyView, type MissionView, type NodeStatus, type ThoughtKind } from "./missionViewTypes";

const MAX_THOUGHTS = 400;
const MAX_LIST = 120;

function push<T>(list: T[], item: T, max = MAX_LIST): T[] {
  const next = list.length >= max ? list.slice(list.length - max + 1) : list.slice();
  next.push(item);
  return next;
}

function thought(
  v: MissionView,
  e: NexusEvent,
  kind: ThoughtKind,
  title: string,
  body?: string,
  ok?: boolean,
): MissionView {
  // merge consecutive token-less streamed thoughts? keep simple: one item per event
  return {
    ...v,
    thoughts: push(
      v.thoughts,
      { id: e.id, seq: e.seq, ts: e.ts, kind, agent: e.agent_id ?? null, title, body, ok },
      MAX_THOUGHTS,
    ),
  };
}

export function reduceMission(view: MissionView, raw: NexusEvent): MissionView {
  const e = canonicalEvent(raw);
  if (e.seq <= view.lastSeq && view.missionId === e.mission_id) return view;
  let v: MissionView = { ...view, lastSeq: Math.max(view.lastSeq, e.seq), missionId: e.mission_id ?? view.missionId };

  const agent = robotFor(e);
  if (agent) {
    const prev = v.robots[agent] ?? initialRobot(e.ts * 1000);
    v = { ...v, robots: { ...v.robots, [agent]: nextRobot(prev, e) } };
  }

  switch (e.type) {
    case "mission.created":
      return { ...v, title: e.payload.title, status: "running" };
    case "mission.started":
      return thought(
        { ...v, status: "running", interrupt: null, error: null },
        e,
        "system",
        e.payload.resumed ? "Mission resumed from checkpoint" : "Mission started",
      );
    case "mission.completed":
      return thought(
        { ...v, status: "completed", outcome: e.payload.outcome, currentNode: null },
        e,
        "system",
        `Completed: ${e.payload.outcome}`,
        e.payload.summary,
        e.payload.outcome === "success",
      );
    case "mission.failed":
      return thought(
        { ...v, status: "failed", error: e.payload.error, currentNode: null },
        e,
        "system",
        `Failed${e.payload.node ? ` in ${e.payload.node}` : ""}`,
        e.payload.error,
        false,
      );
    case "mission.cancelled":
      return { ...v, status: "cancelled", currentNode: null };
    case "node.entered": {
      const n = v.nodes[e.payload.node] ?? { status: "idle", visits: 0, lastMs: null };
      return {
        ...v,
        currentNode: e.payload.node.includes(".") ? v.currentNode : e.payload.node,
        nodes: { ...v.nodes, [e.payload.node]: { ...n, status: "active", visits: n.visits + 1 } },
      };
    }
    case "node.exited": {
      const n = v.nodes[e.payload.node] ?? { status: "idle", visits: 1, lastMs: null };
      const status: NodeStatus =
        e.payload.status === "ok" ? "done" : e.payload.status === "error" ? "error" : "interrupted";
      return { ...v, nodes: { ...v.nodes, [e.payload.node]: { ...n, status, lastMs: e.payload.duration_ms } } };
    }
    case "edge.taken":
      v = { ...v, edges: push(v.edges, { ...e.payload, ts: e.ts, seq: e.seq }, 60) };
      return thought(v, e, "route", `${e.payload.source} → ${e.payload.target}`, e.payload.label);
    case "plan.created":
      return thought(
        { ...v, plan: e.payload },
        e,
        "plan",
        `Plan r${e.payload.revision} (${e.payload.source})`,
        e.payload.steps.map((s) => `• ${String(s.title)}`).join("\n"),
      );
    case "handoff":
      v = { ...v, handoffs: push(v.handoffs, { ...e.payload, ts: e.ts, seq: e.seq }, 40) };
      return thought(v, e, "handoff", `${e.payload.source} → ${e.payload.target}`, e.payload.reason);
    case "send.fanout":
      return {
        ...v,
        fanouts: push(v.fanouts, { count: e.payload.count, items: e.payload.items ?? [], ts: e.ts, seq: e.seq }, 30),
      };
    case "reducer.merged":
      return { ...v, merges: push(v.merges, { ...e.payload, node: e.node ?? null, seq: e.seq }, 80) };
    case "checkpoint.saved":
      // a resumed run re-announces the checkpoint it resumed from
      if (v.checkpoints.some((c) => c.id === e.payload.checkpoint_id)) return v;
      return {
        ...v,
        checkpoints: push(
          v.checkpoints,
          { id: e.payload.checkpoint_id, step: e.payload.step, next: e.payload.next, ts: e.ts, seq: e.seq },
          500,
        ),
      };
    case "agent.thinking":
      return thought(v, e, "thought", "Thought", e.payload.text);
    case "agent.action":
      return thought(v, e, "action", `Action · ${e.payload.tool}`, JSON.stringify(e.payload.args));
    case "agent.observation":
      return thought(v, e, "observation", `Observation · ${e.payload.tool}`, e.payload.summary, e.payload.ok);
    case "agent.final":
      return thought(v, e, "final", "Final answer", e.payload.answer, true);
    case "tool.called":
      return {
        ...v,
        toolCalls: {
          ...v.toolCalls,
          [e.payload.call_id]: {
            agent: e.payload.agent_id ?? e.agent_id ?? null,
            tool: `${e.payload.server}.${e.payload.tool}`,
            ts: e.ts,
            done: false,
          },
        },
      };
    case "tool.result": {
      const call = v.toolCalls[e.payload.call_id];
      if (!call) return v;
      return { ...v, toolCalls: { ...v.toolCalls, [e.payload.call_id]: { ...call, done: true, ok: e.payload.ok } } };
    }
    case "retry":
      return thought(
        v,
        e,
        "retry",
        `Retry ${e.payload.attempt}/${e.payload.max_attempts} · ${e.payload.layer}`,
        e.payload.reason,
        false,
      );
    case "llm.call": {
      const who = e.payload.agent_id ?? "system";
      const total = e.payload.prompt_tokens + e.payload.completion_tokens;
      return {
        ...v,
        llm: {
          calls: v.llm.calls + 1,
          prompt: v.llm.prompt + e.payload.prompt_tokens,
          completion: v.llm.completion + e.payload.completion_tokens,
          byAgent: { ...v.llm.byAgent, [who]: (v.llm.byAgent[who] ?? 0) + total },
        },
      };
    }
    case "council.proposal": {
      const prev = v.council.proposals[e.payload.solver_id];
      const council = {
        ...(v.council.verdict ? emptyCouncil() : v.council),
        active: true,
        proposals: {
          ...(v.council.verdict ? {} : v.council.proposals),
          [e.payload.solver_id]: { strategy: e.payload.strategy, summary: e.payload.summary, revised: Boolean(prev) },
        },
      };
      return { ...v, council };
    }
    case "council.masked":
      return { ...v, council: { ...v.council, labels: e.payload.labels } };
    case "council.review":
      return { ...v, council: { ...v.council, reviews: push(v.council.reviews, e.payload, 60) } };
    case "council.round":
      return { ...v, council: { ...v.council, rounds: [...v.council.rounds, e.payload] } };
    case "sandbox.test_result":
      v = { ...v, council: { ...v.council, tests: { ...v.council.tests, [e.payload.target]: e.payload } } };
      return thought(
        v,
        e,
        "test",
        `Sandbox · ${e.payload.target}`,
        e.payload.summary || `${e.payload.passed} passed, ${e.payload.failed} failed`,
        e.payload.ok,
      );
    case "council.verdict":
      v = { ...v, council: { ...v.council, verdict: e.payload, active: false } };
      return thought(
        v,
        e,
        "verdict",
        `Verdict: ${e.payload.winner_label} (${e.payload.winner}) wins`,
        `confidence ${e.payload.confidence} · ${e.payload.dissent}`,
        !e.payload.escalate,
      );
    case "risk.scored":
      return thought(
        { ...v, risk: e.payload },
        e,
        "risk",
        `Risk ${e.payload.level} → ${e.payload.route}`,
        Object.entries(e.payload.factors)
          .map(([k, x]) => `${k} ${x >= 0 ? "+" : ""}${x.toFixed(2)}`)
          .join(" · "),
      );
    case "interrupt.raised":
      return thought(
        { ...v, status: "paused", interrupt: e.payload },
        e,
        "interrupt",
        "Waiting for a human",
        e.payload.summary,
      );
    case "interrupt.resolved":
      return thought(
        { ...v, interrupt: null, status: "running" },
        e,
        "interrupt",
        `Human: ${e.payload.decision} (${e.payload.channel})`,
        undefined,
        e.payload.decision !== "reject",
      );
    case "guardrail.triggered":
      return thought(v, e, "guardrail", `Guardrail · ${e.payload.kind}`, e.payload.detail, false);
    case "memory.pruned":
      v = {
        ...v,
        memory: push(
          v.memory,
          {
            kind: "pruned",
            detail: e.payload.strategy,
            ts: e.ts,
            before: e.payload.before_tokens,
            after: e.payload.after_tokens,
            agent: e.payload.agent_id,
          },
          60,
        ),
      };
      return thought(
        v,
        e,
        "memory",
        `Context pruned (${e.payload.strategy})`,
        `${e.payload.before_tokens} → ${e.payload.after_tokens} tokens`,
      );
    case "memory.summarised":
      return {
        ...v,
        memory: push(
          v.memory,
          {
            kind: "summarised",
            detail: e.payload.summary,
            ts: e.ts,
            before: e.payload.before_tokens,
            after: e.payload.after_tokens,
            agent: e.payload.agent_id,
          },
          60,
        ),
      };
    case "memory.stored":
      v = {
        ...v,
        memory: push(v.memory, { kind: "stored", detail: `${e.payload.collection}: ${e.payload.title}`, ts: e.ts }, 60),
      };
      return thought(v, e, "memory", `Stored in ${e.payload.collection}`, e.payload.title, true);
    case "memory.recalled":
      v = {
        ...v,
        memory: push(
          v.memory,
          { kind: "recalled", detail: `${e.payload.collection}: ${e.payload.query}`, ts: e.ts },
          60,
        ),
      };
      return thought(
        v,
        e,
        "memory",
        `Recalled from ${e.payload.collection}`,
        e.payload.hits.map((h) => `• ${String(h.title)}`).join("\n"),
      );
    case "email.sent":
      return thought(
        v,
        e,
        "tool",
        `Email ${e.payload.status === "sent" ? "sent" : "queued in outbox"}`,
        `${e.payload.to}: ${e.payload.subject}`,
        e.payload.status === "sent",
      );
    default:
      return v;
  }
}

export function reduceAll(events: NexusEvent[], missionId: string | null = null): MissionView {
  return events.reduce(reduceMission, emptyView(missionId));
}
