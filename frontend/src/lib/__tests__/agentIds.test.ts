import { describe, expect, it } from "vitest";
import { canonicalEvent, canonicalId } from "../agentIds";

describe("legacy agent ids", () => {
  it("maps pre-rename ids and leaves current ones alone", () => {
    expect(canonicalId("ronin_a")).toBe("blaze");
    expect(canonicalId("forge")).toBe("forge");
  });

  it("rewrites agent fields in old events without touching other text", () => {
    const e = { agent_id: "shogun", payload: { source: "shogun", target: "kuro", reason: "watch kuro" } };
    expect(canonicalEvent(e)).toEqual({
      agent_id: "commander",
      payload: { source: "commander", target: "hawk", reason: "watch kuro" },
    });
    const fresh = { agent_id: "sage", payload: { x: 1 } };
    expect(canonicalEvent(fresh)).toBe(fresh);
  });
});
