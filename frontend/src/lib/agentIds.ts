/**
 * Agent ids used before the English rename. Missions recorded earlier still carry them in
 * their events and checkpoints, so the UI maps them onto today's robots when it reads them.
 */
export const LEGACY_IDS: Record<string, string> = {
  shogun: "commander",
  sensei: "sage",
  kagemi: "echo",
  kanji: "quill",
  tetsu: "forge",
  mamoru: "aegis",
  ronin_a: "blaze",
  ronin_b: "volt",
  ronin_c: "frost",
  hakari: "arbiter",
  kiri: "vex",
  hikyaku: "swift",
  kuro: "hawk",
  hikari: "nova",
};

export const canonicalId = (id: string): string => LEGACY_IDS[id] ?? id;

/** Rewrite legacy ids in an event's agent fields (top level and one level into the payload). */
export function canonicalEvent<E extends { agent_id?: string | null; payload: unknown }>(e: E): E {
  const p = e.payload as Record<string, unknown> | null;
  const hasLegacy =
    (e.agent_id != null && e.agent_id in LEGACY_IDS) ||
    (p != null && Object.values(p).some((v) => typeof v === "string" && v in LEGACY_IDS));
  if (!hasLegacy) return e;
  const payload = p
    ? Object.fromEntries(Object.entries(p).map(([k, v]) => [k, typeof v === "string" ? canonicalId(v) : v]))
    : p;
  return { ...e, agent_id: e.agent_id == null ? e.agent_id : canonicalId(e.agent_id), payload };
}
