/**
 * Chart palette for the dark lacquer surface (#1e0f0e). Validated with the dataviz
 * validator: lightness band, chroma, CVD separation, normal-vision floor, contrast — all pass.
 * Status colours (jade/amber/red) are reserved for state and never used as series.
 */
export const SERIES = ["#1f9ba6", "#c0761c", "#8470dd", "#c95a75"] as const;

export const AXIS = { stroke: "rgba(201,178,163,0.35)", fontSize: 11, tick: { fill: "#c9b2a3" } };
export const GRID = "rgba(247,164,64,0.08)";

export const TOOLTIP = {
  contentStyle: {
    background: "rgba(30,15,14,0.95)",
    border: "1px solid rgba(247,164,64,0.35)",
    borderRadius: 8,
    fontSize: 12,
    color: "#f6ebe0",
  },
  labelStyle: { color: "#c9b2a3" },
  itemStyle: { color: "#f6ebe0" },
  cursor: { fill: "rgba(247,164,64,0.06)", stroke: "rgba(247,164,64,0.3)" },
};
