/**
 * Hand-tuned "snake" layout for the orchestrator graph: the understanding/delegation
 * band runs left→right, the decision/action band returns right→left beneath it.
 * Unknown nodes (future additions) are placed on a spill-over row.
 */
export const POSITIONS: Record<string, { x: number; y: number }> = {
  __start__: { x: 0, y: 70 },
  intake: { x: 140, y: 60 },
  rewrite: { x: 310, y: 60 },
  route: { x: 480, y: 60 },
  clarify: { x: 400, y: -90 },
  plan: { x: 650, y: 60 },
  assemble: { x: 820, y: 60 },
  dispatch: { x: 990, y: 60 },
  worker: { x: 1160, y: -60 },
  collect: { x: 1330, y: 60 },
  council: { x: 1330, y: 320 },
  synthesize: { x: 1330, y: 470 },
  validate: { x: 1150, y: 320 },
  risk_gate: { x: 970, y: 320 },
  dry_run: { x: 970, y: 470 },
  approval: { x: 790, y: 320 },
  execute: { x: 610, y: 320 },
  verify: { x: 430, y: 320 },
  rollback: { x: 430, y: 470 },
  memory_write: { x: 250, y: 320 },
  report: { x: 80, y: 320 },
  __end__: { x: 0, y: 470 },
};

export function positionOf(id: string, i: number): { x: number; y: number } {
  return POSITIONS[id] ?? { x: 100 + i * 170, y: 640 };
}
