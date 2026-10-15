import { memo } from "react";

/** Static dojo interior: shoji back wall, wooden floor, the Shogun's dais, the
 * Armory rack and the roof beam Kuro sits on. Pure SVG, no animation. */
export const DojoScene = memo(function DojoScene() {
  const planks = Array.from({ length: 9 }, (_, i) => i);
  const shoji = Array.from({ length: 8 }, (_, i) => i);
  return (
    <svg viewBox="0 0 1000 560" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3a1f14" />
          <stop offset="1" stopColor="#1c0e0a" />
        </linearGradient>
        <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="rgba(255,208,138,0.10)" />
          <stop offset="1" stopColor="rgba(255,208,138,0.03)" />
        </linearGradient>
        <radialGradient id="sunspill" cx="0.5" cy="0" r="0.7">
          <stop offset="0" stopColor="rgba(247,164,64,0.35)" />
          <stop offset="1" stopColor="rgba(247,164,64,0)" />
        </radialGradient>
      </defs>
      {/* back wall with shoji screens (sunset light leaking through) */}
      <rect x="0" y="0" width="1000" height="210" fill="url(#wall)" />
      {shoji.map((i) => (
        <g key={i} opacity={0.5}>
          <rect
            x={i * 125 + 6}
            y={18}
            width={113}
            height={176}
            fill="rgba(255,226,180,0.06)"
            stroke="rgba(247,164,64,0.25)"
          />
          <path
            d={`M${i * 125 + 62},18 v176 M${i * 125 + 6},77 h113 M${i * 125 + 6},136 h113`}
            stroke="rgba(247,164,64,0.18)"
          />
        </g>
      ))}
      <rect x="0" y="0" width="1000" height="14" fill="#140909" />
      <rect x="0" y="198" width="1000" height="12" fill="#2a130d" />
      {/* floor */}
      <path d="M0,210 L1000,210 L1000,560 L0,560 Z" fill="url(#floor)" />
      {planks.map((i) => (
        <path key={i} d={`M0,${230 + i * 38} L1000,${230 + i * 38}`} stroke="rgba(0,0,0,0.35)" strokeWidth={1.2} />
      ))}
      <rect x="0" y="210" width="1000" height="350" fill="url(#sunspill)" />
      {/* tatami border for the council arena */}
      <ellipse
        cx={760}
        cy={410}
        rx={190}
        ry={86}
        fill="rgba(200,52,31,0.10)"
        stroke="rgba(247,164,64,0.25)"
        strokeDasharray="4 6"
      />
      {/* the Shogun's dais */}
      <path d="M380,150 L620,150 L660,190 L340,190 Z" fill="#2b140d" stroke="rgba(247,164,64,0.4)" />
      <rect x="340" y="190" width="320" height="16" fill="#1e0d08" />
      {/* armory rack (bottom-left) */}
      <g transform="translate(18 418)">
        <rect x="0" y="0" width="110" height="120" rx="6" fill="#241109" stroke="rgba(247,164,64,0.35)" />
        {[0, 1, 2, 3, 4].map((i) => (
          <path
            key={i}
            d={`M${14 + i * 20},14 v92`}
            stroke="#c9b2a3"
            strokeOpacity={0.45}
            strokeWidth={3}
            strokeLinecap="round"
          />
        ))}
        <text x="55" y="136" textAnchor="middle" fontSize="13" fill="rgba(247,164,64,0.7)">
          ARMORY · MCP
        </text>
      </g>
      {/* roof beam where Kuro keeps watch */}
      <path d="M840,0 L1000,0 L1000,40 L870,40 Z" fill="#140909" />
    </svg>
  );
});
