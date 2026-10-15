import { describe, expect, it } from "vitest";
import { pagodaPath, pine, seeded } from "../geometry";

describe("scenery geometry", () => {
  it("is deterministic so SSR and client markup match", () => {
    expect(pine(100, 900, 300, 7)).toEqual(pine(100, 900, 300, 7));
    const a = seeded(42);
    const b = seeded(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("draws one wall and one roof per tier plus a ringed spire", () => {
    const closed = pagodaPath(0, 100, 100, 3).match(/Z/g) ?? [];
    expect(closed).toHaveLength(3 * 2 + 1 + 4);
  });
});
