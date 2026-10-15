/**
 * Hand-tuned four-row "snake" layout for the orchestrator graph, compact enough to stay
 * readable when fitted: understand → delegate → decide/act → remember, alternating direction.
 * Unknown nodes (future additions) are placed on a spill-over row.
 */
export const POSITIONS: Record<string, { x: number; y: number }> = {
  // row 1, left → right: understand the task
  __start__: { x: -80, y: 8 },
  intake: { x: 40, y: 0 },
  rewrite: { x: 220, y: 0 },
  route: { x: 400, y: 0 },
  clarify: { x: 400, y: -110 },
  plan: { x: 580, y: 0 },
  assemble: { x: 760, y: 0 },
  // row 2, right → left: delegate and deliberate
  dispatch: { x: 760, y: 170 },
  worker: { x: 580, y: 170 },
  collect: { x: 400, y: 170 },
  council: { x: 220, y: 170 },
  synthesize: { x: 40, y: 170 },
  // row 3, left → right: decide and act
  validate: { x: 40, y: 340 },
  risk_gate: { x: 220, y: 340 },
  dry_run: { x: 220, y: 450 },
  approval: { x: 400, y: 340 },
  execute: { x: 580, y: 340 },
  verify: { x: 760, y: 340 },
  // row 4, right → left: recover, remember, report
  rollback: { x: 760, y: 450 },
  memory_write: { x: 580, y: 540 },
  report: { x: 400, y: 540 },
  __end__: { x: 260, y: 548 },
};

export function positionOf(id: string, i: number): { x: number; y: number } {
  return POSITIONS[id] ?? { x: 40 + (i % 5) * 180, y: 660 };
}
