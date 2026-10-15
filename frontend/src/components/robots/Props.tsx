/** Hand-held props, drawn around the right hand at (78, 84) in robot space. */
export function Prop({ kind, color }: { kind: string; color: string }) {
  switch (kind) {
    case "war_fan": // gunbai: lacquered paddle with a sun disc
      return (
        <g transform="translate(76 52) rotate(18)">
          <rect x={-1.2} y={10} width={2.4} height={20} rx={1} fill="#5a3a1a" />
          <path
            d="M0,-6 C11,-6 14,4 9,13 L-9,13 C-14,4 -11,-6 0,-6 Z"
            fill="#f7a440"
            stroke="#7a4a12"
            strokeWidth={1}
          />
          <circle cx={0} cy={4} r={4.2} fill="#c8341f" />
          <circle cx={0} cy={4} r={7.5} fill="none" stroke="#ffd08a" strokeOpacity={0.6} />
        </g>
      );
    case "scroll":
      return (
        <g transform="translate(74 74) rotate(-20)">
          <rect x={-2} y={0} width={18} height={9} rx={2} fill="#f3e3c3" stroke="#a3793f" strokeWidth={0.8} />
          <rect x={-4} y={-1} width={3} height={11} rx={1.5} fill="#8e1b17" />
          <rect x={15} y={-1} width={3} height={11} rx={1.5} fill="#8e1b17" />
          <path d="M2,3 h10 M2,6 h7" stroke="#a3793f" strokeWidth={0.7} />
        </g>
      );
    case "lens":
      return (
        <g transform="translate(78 70)">
          <rect x={4} y={9} width={3} height={11} rx={1.5} fill="#5a3a1a" transform="rotate(-35 5 9)" />
          <circle cx={0} cy={0} r={7.5} fill="rgba(79,227,240,0.18)" stroke="#d9c38a" strokeWidth={2.2} />
          <path d="M-3,-3 q2,-2 4,-1" stroke="white" strokeWidth={1} fill="none" opacity={0.8} />
        </g>
      );
    case "brush":
      return (
        <g transform="translate(78 64) rotate(25)">
          <rect x={-1.5} y={0} width={3} height={20} rx={1.5} fill="#3b2a1a" />
          <path d="M-2.5,20 Q0,30 2.5,20 Z" fill="#141414" />
        </g>
      );
    case "hammer":
      return (
        <g transform="translate(80 70) rotate(-25)">
          <rect x={-1.4} y={-2} width={2.8} height={18} rx={1.2} fill="#6b4a24" />
          <rect x={-7} y={-6} width={14} height={7} rx={2} fill="#9aa3ad" stroke="#5f6670" strokeWidth={0.8} />
        </g>
      );
    case "shield":
      return (
        <g transform="translate(80 78)">
          <path
            d="M0,-12 L10,-8 C10,4 6,10 0,14 C-6,10 -10,4 -10,-8 Z"
            fill={color}
            stroke="#1e5e3f"
            strokeWidth={1.2}
          />
          <path d="M0,-6 v12 M-5,0 h10" stroke="#f5f2ec" strokeWidth={1.6} opacity={0.85} />
        </g>
      );
    case "katana":
      return (
        <g transform="translate(78 82) rotate(-55)">
          <rect x={-1} y={-34} width={2.2} height={32} rx={1} fill="#d8dee6" />
          <rect x={-4} y={-3} width={8} height={2.2} rx={1} fill="#d9c38a" />
          <rect x={-1.6} y={-1} width={3.2} height={9} rx={1.4} fill="#2b1a10" />
        </g>
      );
    case "scale":
      return (
        <g transform="translate(80 62)">
          <rect x={-0.9} y={0} width={1.8} height={18} fill="#d9c38a" />
          <rect x={-11} y={-1} width={22} height={1.6} rx={0.8} fill="#d9c38a" />
          <path d="M-11,0 l-3,7 h6 Z M11,0 l-3,7 h6 Z" fill="#d9c38a" opacity={0.9} />
        </g>
      );
    case "envelope":
      return (
        <g transform="translate(12 62)">
          <rect x={0} y={0} width={14} height={10} rx={1.5} fill="#f5f2ec" stroke="#c8341f" strokeWidth={1} />
          <path d="M0,0 l7,6 l7,-6" fill="none" stroke="#c8341f" strokeWidth={1} />
        </g>
      );
    case "lantern":
      return (
        <g transform="translate(80 70)">
          <path d="M0,-6 v-4" stroke="#3b2a1a" strokeWidth={1} />
          <ellipse cx={0} cy={2} rx={6} ry={8} fill="#f2662a" />
          <ellipse cx={0} cy={2} rx={6} ry={8} fill="url(#nexus-lantern)" />
          <rect x={-4} y={-7} width={8} height={2} rx={1} fill="#3b2a1a" />
          <rect x={-4} y={9} width={8} height={2} rx={1} fill="#3b2a1a" />
        </g>
      );
    default:
      return null;
  }
}

/** The Shogun's gold kabuto crest (maedate) and short cape. */
export function ShogunRegalia() {
  return {
    crest: (
      <g>
        <path d="M50,12 C40,0 30,-6 22,-10 C34,-2 42,6 47,14 Z" fill="#f7a440" stroke="#9a5f12" strokeWidth={0.8} />
        <path d="M50,12 C60,0 70,-6 78,-10 C66,-2 58,6 53,14 Z" fill="#f7a440" stroke="#9a5f12" strokeWidth={0.8} />
        <circle cx={50} cy={13} r={3.2} fill="#c8341f" stroke="#ffd08a" strokeWidth={0.8} />
      </g>
    ),
    cape: <path d="M30,66 C24,84 22,98 26,104 L74,104 C78,98 76,84 70,66 Z" fill="#8e1b17" opacity={0.95} />,
  };
}
