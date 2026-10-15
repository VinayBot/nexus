import { memo } from "react";
import { cityRow, domePath, rowPath, windowsOf } from "./geometry";

const W = 1600;
const H = 900;

const FAR = cityRow(11, W, 120, 300, 180);
const MID = cityRow(23, W, 90, 230, 240);
const NEAR = cityRow(5, W, 50, 150, 300);
const LIGHTS = windowsOf(MID, 800, 9, 0.1);

/** Far → near city silhouette layers with a few twinkling windows. Parent may parallax it. */
export const Skyline = memo(function Skyline({ className }: { className?: string }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMax slice" className={className} aria-hidden>
      {/* distant towers in the haze */}
      <g fill="var(--silhouette)" opacity={0.32}>
        <path d={rowPath(FAR, 740)} />
        <path d="M0,740 L1600,740 L1600,900 L0,900 Z" />
      </g>
      {/* mid layer: towers, domes and lit windows */}
      <g fill="var(--silhouette)" opacity={0.65}>
        <path d={rowPath(MID, 800)} />
        <path d={`${domePath(420, 800, 90)} ${domePath(1190, 800, 120)}`} />
        <path d="M0,800 L1600,800 L1600,900 L0,900 Z" />
      </g>
      <g className="perf-hide">
        {LIGHTS.map((l, i) => (
          <rect
            key={i}
            x={l.x}
            y={l.y}
            width={4}
            height={6}
            fill={i % 5 === 0 ? "var(--cyan)" : "var(--sun-core)"}
            opacity={0.55}
            className="animate-glow"
            style={{ animationDelay: `${l.d}s`, animationDuration: `${3 + (i % 4)}s` }}
          />
        ))}
      </g>
      {/* near layer: rooftops and a sky bridge */}
      <g fill="var(--silhouette)">
        <path d={rowPath(NEAR, 870)} />
        <path d="M180,800 h260 v8 h-260 Z M1180,790 h240 v8 h-240 Z" />
        <path d="M0,860 Q400,850 800,868 T1600,858 L1600,900 L0,900 Z" />
      </g>
    </svg>
  );
});
