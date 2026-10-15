/**
 * Chart palette for the dark panel surface (#0d101b). Validated with the dataviz
 * validator: lightness band, chroma, CVD separation, normal-vision floor, contrast — all pass.
 * Status colours (jade/amber/red) are reserved for state and never used as series.
 */
export const SERIES = ["#1f9ba6", "#c0761c", "#8470dd", "#c95a75"] as const;

export const AXIS = { stroke: "rgba(148,163,210,0.3)", fontSize: 11, tick: { fill: "#a3abc2" } };
export const GRID = "rgba(79,227,240,0.07)";

export const TOOLTIP = {
  contentStyle: {
    background: "rgba(10,13,24,0.95)",
    border: "1px solid rgba(79,227,240,0.35)",
    borderRadius: 8,
    fontSize: 12,
    color: "#eef1f8",
  },
  labelStyle: { color: "#a3abc2" },
  itemStyle: { color: "#eef1f8" },
  cursor: { fill: "rgba(79,227,240,0.06)", stroke: "rgba(79,227,240,0.3)" },
};
