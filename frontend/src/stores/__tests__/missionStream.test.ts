import { describe, expect, it } from "vitest";
import type { NexusEvent } from "@/lib/events";
import { useStreams } from "../missionStream";

const ev = (seq: number, type: string, payload: Record<string, unknown>): NexusEvent =>
  ({
    id: `e${seq}`,
    seq,
    mission_id: "m",
    thread_id: "m",
    checkpoint_id: null,
    ts: 1000 + seq,
    agent_id: null,
    node: null,
    type,
    payload,
  }) as NexusEvent;

const history = [
  ev(1, "mission.started", { title: "t", task: "t", playbook: null }),
  ev(2, "node.started", { node: "intake" }),
  ev(3, "node.completed", { node: "intake", duration_ms: 3, updates: [] }),
  ev(4, "edge.taken", { source: "intake", target: "rewrite", label: null }),
];

describe("mission stream store", () => {
  it("applies a batch in one update with the same result as one-by-one", () => {
    useStreams.getState().reset("a");
    useStreams.getState().reset("b");
    let updates = 0;
    const unsub = useStreams.subscribe(() => (updates += 1));
    useStreams.getState().applyMany("a", history);
    unsub();
    history.forEach((e) => useStreams.getState().apply("b", e));
    const { views, events } = useStreams.getState();
    expect(updates).toBe(1);
    expect(views.a!.lastSeq).toBe(4);
    expect({ ...views.a, missionId: "x" }).toEqual({ ...views.b, missionId: "x" });
    expect(events.a).toHaveLength(4);
  });

  it("ignores duplicates when the live socket overlaps the loaded history", () => {
    useStreams.getState().reset("c");
    useStreams.getState().applyMany("c", history);
    useStreams.getState().applyMany("c", history.slice(2));
    expect(useStreams.getState().events.c).toHaveLength(4);
  });
});
