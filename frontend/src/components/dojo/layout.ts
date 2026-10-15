/** Where each robot stands on the Dojo Floor (percent of the floor box). */
export const POSTS: Record<string, { x: number; y: number; z?: number }> = {
  shogun: { x: 50, y: 22, z: 3 },
  sensei: { x: 30, y: 30 },
  kanji: { x: 70, y: 30 },
  kagemi: { x: 15, y: 60 },
  tetsu: { x: 31, y: 66 },
  mamoru: { x: 47, y: 68 },
  hikyaku: { x: 89, y: 34 },
  kuro: { x: 91, y: 7 },
  hakari: { x: 74, y: 50 },
  ronin_a: { x: 63, y: 70 },
  ronin_b: { x: 74, y: 78 },
  ronin_c: { x: 85, y: 70 },
  kiri: { x: 93, y: 56 },
};

/** The Armory tool station (tool-call beams point here). */
export const ARMORY = { x: 6, y: 86 };
/** Test lanterns row. */
export const LANTERNS = { x: 54, y: 93 };

export function postOf(id: string, index = 0): { x: number; y: number; z?: number } {
  return POSTS[id] ?? { x: 12 + ((index * 17) % 76), y: 44 };
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
  { id: "approval", label: "Seal" },
  { id: "execute", label: "Execute" },
  { id: "verify", label: "Verify" },
  { id: "memory_write", label: "Memory" },
  { id: "report", label: "Report" },
];
