/**
 * Procedural silhouette geometry for the dojo skyline. Everything is generated
 * from a few numbers so the artwork is original and resolution independent.
 */

/** One curved-eave roof tier: wide flared eaves, steep centre. */
function roofTier(cx: number, y: number, w: number, h: number): string {
  const ov = w * 0.16; // eave overhang past the walls
  const l = cx - w / 2 - ov;
  const r = cx + w / 2 + ov;
  return [
    `M${l},${y}`,
    `Q${cx - w * 0.42},${y - h * 0.18} ${cx - w * 0.26},${y - h * 0.62}`,
    `L${cx - w * 0.1},${y - h}`,
    `L${cx + w * 0.1},${y - h}`,
    `L${cx + w * 0.26},${y - h * 0.62}`,
    `Q${cx + w * 0.42},${y - h * 0.18} ${r},${y}`,
    `L${r - ov * 0.4},${y + h * 0.12}`,
    `L${l + ov * 0.4},${y + h * 0.12}`,
    "Z",
  ].join(" ");
}

/** A multi-tier pagoda standing on `baseY`; returns one path string. */
export function pagodaPath(cx: number, baseY: number, width: number, tiers: number): string {
  const parts: string[] = [];
  let y = baseY;
  let w = width;
  const tierH = width * 0.42;
  for (let i = 0; i < tiers; i++) {
    const wallH = tierH * 0.55;
    // walls
    parts.push(`M${cx - w * 0.36},${y} h${w * 0.72} v${-wallH} h${-w * 0.72} Z`);
    y -= wallH;
    parts.push(roofTier(cx, y, w, tierH * 0.6));
    y -= tierH * 0.6;
    w *= 0.8;
  }
  // spire (sōrin) with rings
  const sw = width * 0.035;
  parts.push(`M${cx - sw},${y} h${sw * 2} v${-width * 0.55} h${-sw * 2} Z`);
  for (let k = 1; k <= 4; k++) {
    const ry = y - (width * 0.55 * k) / 5;
    parts.push(`M${cx - sw * 2.6},${ry} h${sw * 5.2} v${-sw * 0.9} h${-sw * 5.2} Z`);
  }
  return parts.join(" ");
}

/** A low temple hall: one wide roof over a long wall. */
export function hallPath(cx: number, baseY: number, width: number): string {
  const wallH = width * 0.22;
  return [
    `M${cx - width * 0.42},${baseY} h${width * 0.84} v${-wallH} h${-width * 0.84} Z`,
    roofTier(cx, baseY - wallH, width, width * 0.3),
  ].join(" ");
}

/** Deterministic pseudo-random generator so SSR and client render the same art. */
export function seeded(seed: number): () => number {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export interface Ellipse {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
}

/** A Japanese-pine silhouette: a leaning trunk carrying flat foliage pads. */
export function pine(x: number, baseY: number, height: number, seed: number) {
  const rnd = seeded(seed);
  const lean = (rnd() - 0.5) * height * 0.35;
  const topX = x + lean;
  const topY = baseY - height;
  const tw = height * 0.035;
  const trunk = `M${x - tw},${baseY} Q${x + lean * 0.2},${baseY - height * 0.5} ${topX - tw * 0.4},${topY} L${topX + tw * 0.4},${topY} Q${x + lean * 0.2 + tw * 2},${baseY - height * 0.5} ${x + tw},${baseY} Z`;
  const pads: Ellipse[] = [];
  const n = 4 + Math.floor(rnd() * 3);
  for (let i = 0; i < n; i++) {
    const t = 0.35 + (i / n) * 0.7;
    const side = i % 2 === 0 ? -1 : 1;
    const px = x + lean * t + side * height * (0.12 + rnd() * 0.18);
    const py = baseY - height * t;
    pads.push({ cx: px, cy: py, rx: height * (0.16 + rnd() * 0.1), ry: height * (0.05 + rnd() * 0.025) });
  }
  pads.push({ cx: topX, cy: topY, rx: height * 0.2, ry: height * 0.07 });
  return { trunk, pads };
}
