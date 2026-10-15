"use client";

import { useUi } from "@/stores/ui";
import { Embers } from "./Embers";
import { Skyline } from "./Skyline";

/** Birds drawn as tiny wing strokes, flying in a loose V. */
function Birds() {
  const flock = [
    [0, 0],
    [-26, 12],
    [-50, 22],
    [24, 14],
    [46, 26],
    [-8, 34],
  ];
  return (
    <svg
      viewBox="0 0 120 60"
      className="perf-hide absolute top-[18%] left-0 w-28 opacity-70 [animation:drift-x_70s_linear_infinite] motion-reduce:hidden"
      aria-hidden
    >
      {flock.map(([x, y], i) => (
        <path
          key={i}
          d={`M${60 + x! - 6},${10 + y!} q3,-4 6,0 q3,-4 6,0`}
          stroke="var(--silhouette)"
          strokeWidth={1.6}
          fill="none"
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}

function Clouds() {
  const bands = [
    { top: "22%", w: "38%", delay: "0s", o: 0.28 },
    { top: "33%", w: "52%", delay: "-40s", o: 0.2 },
    { top: "46%", w: "30%", delay: "-70s", o: 0.25 },
  ];
  return (
    <>
      {bands.map((b, i) => (
        <div
          key={i}
          aria-hidden
          className="perf-hide absolute h-6 rounded-full blur-md"
          style={{
            top: b.top,
            width: b.w,
            opacity: b.o,
            background: "linear-gradient(90deg, transparent, var(--sun-glow), transparent)",
            animation: `drift-x var(--cloud-speed) linear infinite`,
            animationDelay: b.delay,
          }}
        />
      ))}
    </>
  );
}

/**
 * Full-viewport sunset scene behind the app. Colours come from CSS variables
 * selected by `data-theme` and `data-sky`, so the sky reacts to system state.
 */
export function SkyBackdrop({ embers = true }: { embers?: boolean }) {
  const perf = useUi((s) => s.performanceMode);
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute inset-0 transition-[background] duration-[2000ms]"
        style={{
          background:
            "linear-gradient(180deg, var(--sky-top) 0%, var(--sky-mid) 38%, var(--sky-low) 62%, var(--sky-horizon) 80%, var(--silhouette) 100%)",
        }}
      />
      {/* sun with layered glow */}
      <div className="absolute left-1/2 top-[56%] -translate-x-1/2 -translate-y-1/2">
        <div
          className="absolute left-1/2 top-1/2 h-[90vmin] w-[90vmin] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40 blur-3xl"
          style={{ background: "radial-gradient(circle, var(--sun-glow) 0%, transparent 65%)" }}
        />
        <div
          className="animate-sun-pulse h-[46vmin] w-[46vmin] rounded-full"
          style={{
            background:
              "radial-gradient(circle at 50% 45%, var(--sun-glow) 0%, var(--sun-color) 55%, var(--ember) 100%)",
            boxShadow: "0 0 120px 30px color-mix(in srgb, var(--sun-color) 45%, transparent)",
          }}
        />
      </div>
      <Clouds />
      <Birds />
      <Skyline className="absolute inset-x-0 bottom-0 h-[62vh] w-full" />
      {/* darken the bottom so panels stay legible */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/10 via-black/25 to-black/70" />
      {embers && !perf && <Embers className="absolute inset-0 h-full w-full" max={36} />}
    </div>
  );
}
