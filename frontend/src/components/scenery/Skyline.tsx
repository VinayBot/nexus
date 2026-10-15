import { memo } from "react";
import { hallPath, pagodaPath, pine } from "./geometry";

const W = 1600;
const H = 900;

/** Far → near silhouette layers. Pure SVG, no animation; parent may parallax it. */
export const Skyline = memo(function Skyline({ className }: { className?: string }) {
  const pines = [pine(120, 900, 330, 3), pine(260, 900, 220, 11), pine(1420, 900, 360, 7), pine(1530, 900, 240, 19)];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMax slice" className={className} aria-hidden>
      {/* distant mountain ridge */}
      <path
        d="M0,700 C180,640 300,610 430,650 C560,690 640,600 780,610 C930,620 1010,690 1160,660 C1300,630 1420,600 1600,650 L1600,900 L0,900 Z"
        fill="var(--silhouette)"
        opacity={0.35}
      />
      {/* mid layer: temple halls */}
      <g fill="var(--silhouette)" opacity={0.62}>
        <path d={hallPath(330, 760, 260)} />
        <path d={hallPath(1240, 770, 300)} />
        <path d="M0,760 L1600,770 L1600,900 L0,900 Z" />
      </g>
      {/* near layer: pagodas, rooftops, pines */}
      <g fill="var(--silhouette)">
        <path d={pagodaPath(1050, 840, 150, 5)} />
        <path d={pagodaPath(560, 860, 110, 3)} />
        <path d={hallPath(800, 880, 420)} />
        {pines.map((p, i) => (
          <g key={i}>
            <path d={p.trunk} />
            {p.pads.map((e, j) => (
              <ellipse key={j} cx={e.cx} cy={e.cy} rx={e.rx} ry={e.ry} />
            ))}
          </g>
        ))}
        <path d="M0,850 Q400,830 800,860 T1600,845 L1600,900 L0,900 Z" />
      </g>
    </svg>
  );
});
