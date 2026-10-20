import { memo } from "react";
import { cityRow, rowPath } from "@/components/scenery/geometry";

const SKYLINE = rowPath(cityRow(31, 1000, 30, 90, 90), 196);
const MULLIONS = Array.from({ length: 7 }, (_, i) => 70 + i * 143);
const GRID_X = Array.from({ length: 17 }, (_, i) => -1100 + i * 200);
const GRID_Y = [228, 252, 284, 326, 380, 446, 528];

/**
 * The command bridge behind the robots: a panoramic sunset window, a glowing grid floor,
 * the Commander's holo-platform, the MCP tools terminal, the arena ring and Hawk's catwalk.
 * Ambient motion only (scan lines, rotating rings); robots carry the real-event animation.
 */
export const CommandDeck = memo(function CommandDeck() {
  return (
    <svg viewBox="0 0 1000 560" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="deck-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--sky-mid)" />
          <stop offset="0.65" stopColor="var(--sky-low)" />
          <stop offset="1" stopColor="var(--sky-horizon)" />
        </linearGradient>
        <radialGradient id="deck-sun" cx="0.5" cy="1" r="0.5">
          <stop offset="0" stopColor="var(--sun-glow)" stopOpacity="0.95" />
          <stop offset="0.35" stopColor="var(--sun-color)" stopOpacity="0.55" />
          <stop offset="1" stopColor="var(--sun-color)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="deck-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1d1a26" />
          <stop offset="1" stopColor="#09080d" />
        </linearGradient>
        <radialGradient id="deck-spill" cx="0.5" cy="0" r="0.75">
          <stop offset="0" stopColor="rgb(var(--gold-rgb) / 0.32)" />
          <stop offset="1" stopColor="rgb(var(--gold-rgb) / 0)" />
        </radialGradient>
        <linearGradient id="deck-scan" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="rgb(var(--accent-soft-rgb) / 0)" />
          <stop offset="1" stopColor="rgb(var(--accent-soft-rgb) / 0.16)" />
        </linearGradient>
      </defs>

      {/* panoramic window: sunset, sun and a distant city */}
      <rect x="0" y="0" width="1000" height="210" fill="url(#deck-sky)" />
      <ellipse cx="500" cy="196" rx="260" ry="150" fill="url(#deck-sun)" className="animate-sun-pulse" />
      <circle cx="500" cy="196" r="46" fill="var(--sun-color)" opacity="0.9" />
      <path d={SKYLINE} fill="var(--silhouette)" opacity="0.85" />
      {MULLIONS.map((x) => (
        <path key={x} d={`M${x},0 L${x - 8},210`} stroke="#131119" strokeWidth="7" />
      ))}
      <rect x="0" y="0" width="1000" height="16" fill="#100e15" />
      <path d="M0,16 H1000" stroke="var(--cyan)" strokeOpacity="0.45" strokeWidth="1.5" className="animate-glow" />
      <rect x="0" y="196" width="1000" height="14" fill="#16141e" />
      <path d="M0,210 H1000" stroke="var(--sun-gold)" strokeOpacity="0.5" />

      {/* grid floor in perspective */}
      <path d="M0,210 L1000,210 L1000,560 L0,560 Z" fill="url(#deck-floor)" />
      <g stroke="var(--cyan)" strokeOpacity="0.13" strokeWidth="1">
        {GRID_X.map((x) => (
          <path key={x} d={`M${500 + (x - 500) * 0.12},210 L${x},560`} />
        ))}
        {GRID_Y.map((y) => (
          <path key={y} d={`M0,${y} H1000`} />
        ))}
      </g>
      <rect x="0" y="210" width="1000" height="350" fill="url(#deck-spill)" />
      <rect x="0" y="210" width="1000" height="60" fill="url(#deck-scan)" className="deck-scan" />

      {/* arena: hex ring where the council debates */}
      <g transform="translate(760 410)">
        <path
          d="M-190,0 L-95,-86 L95,-86 L190,0 L95,86 L-95,86 Z"
          fill="rgb(var(--ember-rgb) / 0.08)"
          stroke="rgb(var(--gold-rgb) / 0.35)"
        />
        <path
          d="M-170,0 L-85,-76 L85,-76 L170,0 L85,76 L-85,76 Z"
          fill="none"
          stroke="var(--cyan)"
          strokeOpacity="0.4"
          strokeDasharray="6 10"
          className="animate-flow"
        />
      </g>

      {/* the Commander's holo-platform */}
      <g transform="translate(500 176)">
        <ellipse rx="130" ry="22" fill="rgb(var(--gold-rgb) / 0.10)" stroke="rgb(var(--gold-rgb) / 0.55)" />
        <ellipse
          rx="96"
          ry="15"
          fill="none"
          stroke="var(--cyan)"
          strokeOpacity="0.55"
          strokeDasharray="10 8"
          className="animate-flow"
        />
        <ellipse rx="60" ry="9" fill="rgb(var(--accent-soft-rgb) / 0.12)" className="animate-glow" />
      </g>

      {/* MCP tools terminal (bottom-left) */}
      <g transform="translate(16 412)">
        <path
          d="M0,10 L10,0 L118,0 L128,10 L128,128 L0,128 Z"
          fill="#121018"
          stroke="rgb(var(--accent-soft-rgb) / 0.5)"
        />
        <rect x="10" y="12" width="108" height="70" rx="3" fill="rgb(var(--accent-soft-rgb) / 0.07)" />
        {[0, 1, 2, 3, 4].map((i) => (
          <rect
            key={i}
            x="18"
            y={20 + i * 12}
            width={40 + ((i * 37) % 60)}
            height="4"
            rx="2"
            fill="var(--cyan)"
            opacity="0.6"
            className="animate-glow"
            style={{ animationDelay: `${i * 0.35}s` }}
          />
        ))}
        {[0, 1, 2].map((i) => (
          <circle key={i} cx={28 + i * 36} cy="102" r="7" fill="none" stroke="var(--sun-gold)" strokeOpacity="0.6" />
        ))}
        <text
          x="64"
          y="146"
          textAnchor="middle"
          fontSize="12"
          letterSpacing="2"
          fill="rgb(var(--accent-soft-rgb) / 0.8)"
        >
          TOOLS · MCP
        </text>
      </g>

      {/* test bay pad (light bars appear here) */}
      <rect x="470" y="508" width="140" height="36" rx="8" fill="rgba(0,0,0,0.35)" stroke="rgba(63,209,139,0.35)" />

      {/* Hawk's catwalk */}
      <path d="M830,16 L1000,16 L1000,62 L860,62 Z" fill="#100e15" stroke="rgba(255,176,32,0.4)" />
      <path
        d="M866,58 H996"
        stroke="var(--warning)"
        strokeOpacity="0.6"
        strokeDasharray="4 6"
        className="animate-flow"
      />
    </svg>
  );
});
