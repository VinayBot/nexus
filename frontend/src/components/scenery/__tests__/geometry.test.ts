import { describe, expect, it } from "vitest";
import { cityRow, seeded, towerPath, windowsOf } from "../geometry";

describe("scenery geometry", () => {
  it("is deterministic so SSR and client markup match", () => {
    expect(cityRow(7, 1600, 100, 300)).toEqual(cityRow(7, 1600, 100, 300));
    const a = seeded(42);
    const b = seeded(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("spans the full width and lowers towers in the sun gap", () => {
    const row = cityRow(3, 1600, 200, 200, 150);
    expect(row.at(-1)!.cx + row.at(-1)!.w / 2).toBeGreaterThanOrEqual(1600);
    const mid = row.find((t) => Math.abs(t.cx - 800) < 150);
    expect(mid?.h).toBeCloseTo(70);
  });

  it("draws a body plus a crown per tower style", () => {
    expect(towerPath(0, 100, 40, 80, "stepped").match(/Z/g)).toHaveLength(4);
    expect(towerPath(0, 100, 40, 80, "spire").match(/Z/g)).toHaveLength(2);
    expect(windowsOf(cityRow(1, 400, 100, 200), 900, 1).length).toBeGreaterThan(0);
  });
});
