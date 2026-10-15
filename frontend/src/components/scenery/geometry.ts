/**
 * Procedural silhouette geometry for the futuristic sunset skyline. Everything is generated
 * from a few numbers so the artwork is original and resolution independent.
 */

/** Deterministic pseudo-random generator so SSR and client render the same art. */
export function seeded(seed: number): () => number {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export type TowerStyle = "block" | "spire" | "stepped" | "dish";

/** One skyscraper standing on `baseY`; returns a path of closed sub-shapes. */
export function towerPath(cx: number, baseY: number, w: number, h: number, style: TowerStyle): string {
  const l = cx - w / 2;
  const top = baseY - h;
  const parts = [`M${l},${baseY} h${w} V${top} h${-w} Z`];
  switch (style) {
    case "spire":
      parts.push(`M${l + w * 0.15},${top} L${cx},${top - h * 0.35} L${l + w * 0.85},${top} Z`);
      break;
    case "stepped":
      parts.push(`M${l + w * 0.15},${top} h${w * 0.7} v${-h * 0.12} h${-w * 0.7} Z`);
      parts.push(`M${l + w * 0.32},${top - h * 0.12} h${w * 0.36} v${-h * 0.1} h${-w * 0.36} Z`);
      parts.push(`M${cx - 1.5},${top - h * 0.22} h3 v${-h * 0.18} h-3 Z`);
      break;
    case "dish":
      parts.push(`M${cx - w * 0.45},${top} a${w * 0.45},${w * 0.3} 0 0,1 ${w * 0.9},0 Z`);
      parts.push(`M${cx - 1.2},${top - w * 0.3} h2.4 v${-h * 0.15} h-2.4 Z`);
      break;
    default:
      parts.push(`M${l + w * 0.7},${top} h3 v${-h * 0.2} h-3 Z`);
  }
  return parts.join(" ");
}

/** A low dome (arcology / observatory). */
export function domePath(cx: number, baseY: number, r: number): string {
  return `M${cx - r},${baseY} a${r},${r * 0.7} 0 0,1 ${r * 2},0 Z M${cx - 1.5},${baseY - r * 0.7} h3 v${-r * 0.4} h-3 Z`;
}

export interface Tower {
  cx: number;
  w: number;
  h: number;
  style: TowerStyle;
}

const STYLES: TowerStyle[] = ["block", "spire", "stepped", "dish"];

/** A row of towers across `width`, with a gap in the middle for the sun. */
export function cityRow(seed: number, width: number, minH: number, maxH: number, gap = 0): Tower[] {
  const rnd = seeded(seed);
  const towers: Tower[] = [];
  let x = 0;
  while (x < width) {
    const w = 34 + rnd() * 70;
    const cx = x + w / 2;
    const centre = Math.abs(cx - width / 2) < gap;
    const h = (minH + rnd() * (maxH - minH)) * (centre ? 0.35 : 1);
    towers.push({ cx, w, h, style: STYLES[Math.floor(rnd() * STYLES.length)]! });
    x += w + rnd() * 14;
  }
  return towers;
}

export const rowPath = (towers: Tower[], baseY: number) =>
  towers.map((t) => towerPath(t.cx, baseY, t.w, t.h, t.style)).join(" ");

/** Lit windows scattered over a tower row (deterministic). */
export function windowsOf(towers: Tower[], baseY: number, seed: number, density = 0.12) {
  const rnd = seeded(seed);
  const out: { x: number; y: number; d: number }[] = [];
  for (const t of towers) {
    const cols = Math.max(1, Math.floor(t.w / 12));
    const rows = Math.floor(t.h / 16);
    for (let c = 0; c < cols; c++)
      for (let r = 1; r < rows; r++)
        if (rnd() < density) out.push({ x: t.cx - t.w / 2 + 6 + c * 12, y: baseY - r * 16, d: rnd() * 6 });
  }
  return out;
}
