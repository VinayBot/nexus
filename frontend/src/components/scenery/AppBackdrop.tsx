"use client";

import { memo } from "react";
import { useUi } from "@/stores/ui";
import { Embers } from "./Embers";
import { Skyline } from "./Skyline";

/** Static star field drawn once as layered radial gradients. */
const STARS = Array.from({ length: 70 }, (_, i) => {
  const x = (i * 137.5) % 100;
  const y = (i * 61.8) % 55;
  const s = i % 7 === 0 ? 1.6 : 1;
  return `radial-gradient(${s}px ${s}px at ${x}% ${y}%, rgb(255 255 255 / ${i % 3 === 0 ? 0.8 : 0.4}), transparent)`;
}).join(",");

/**
 * The in-app background: a void sky with slow sunset aurora, a star field, a glowing
 * horizon behind a city silhouette and a perspective grid rolling toward the viewer.
 * Colours come from tokens, so `data-sky` (calm / incident / healed) and the night
 * theme recolour it. Everything animates with transform/opacity only.
 */
export const AppBackdrop = memo(function AppBackdrop() {
  const perf = useUi((s) => s.performanceMode);
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[var(--bg)]">
      {/* aurora */}
      <div
        className="absolute -top-[30vh] -left-[20vw] h-[90vh] w-[80vw] rounded-full transition-[background] duration-[2000ms] [animation:aurora-a_38s_ease-in-out_infinite]"
        style={{ background: "radial-gradient(closest-side, var(--aura-1), transparent)" }}
      />
      <div
        className="absolute -top-[20vh] right-[-25vw] h-[85vh] w-[75vw] rounded-full transition-[background] duration-[2000ms] [animation:aurora-b_46s_ease-in-out_infinite]"
        style={{ background: "radial-gradient(closest-side, var(--aura-2), transparent)" }}
      />
      <div
        className="absolute top-[25vh] left-[25vw] h-[70vh] w-[60vw] rounded-full transition-[background] duration-[2000ms] [animation:aurora-c_54s_ease-in-out_infinite]"
        style={{ background: "radial-gradient(closest-side, var(--aura-3), transparent)" }}
      />
      <div className="absolute inset-0 opacity-70" style={{ backgroundImage: STARS }} />

      {/* horizon: setting sun glow behind the city */}
      <div
        className="absolute inset-x-0 bottom-0 h-[55vh] transition-[background] duration-[2000ms]"
        style={{ background: "radial-gradient(ellipse 60% 70% at 50% 100%, var(--horizon), transparent 70%)" }}
      />
      <Skyline className="absolute inset-x-0 bottom-[14vh] h-[34vh] w-full opacity-80" />

      {/* perspective grid floor */}
      <div className="absolute inset-x-0 bottom-0 h-[18vh] overflow-hidden [perspective:420px]">
        <div
          className="absolute inset-x-[-50%] -top-16 bottom-0 origin-top [transform:rotateX(62deg)]"
          style={{
            maskImage: "linear-gradient(to bottom, transparent, black 30%)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent, black 30%)",
          }}
        >
          <div
            className="perf-hide absolute inset-x-0 -top-16 bottom-0 [animation:grid-roll_3.5s_linear_infinite]"
            style={{
              backgroundImage:
                "linear-gradient(rgb(255 140 60 / 0.35) 1px, transparent 1px), linear-gradient(90deg, rgb(255 140 60 / 0.35) 1px, transparent 1px)",
              backgroundSize: "64px 64px",
            }}
          />
        </div>
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--sun-gold)] to-transparent opacity-70" />
      </div>

      {/* vignette keeps panels legible */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgb(0_0_0/0.55)_100%)]" />
      {!perf && <Embers className="absolute inset-0 h-full w-full" max={22} glints={0.35} />}
    </div>
  );
});
