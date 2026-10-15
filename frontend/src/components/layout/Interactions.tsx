"use client";

import { useEffect } from "react";

/**
 * Two delegated listeners for the whole app, so no component has to opt in:
 * - the panel under the pointer gets --mx/--my for its spotlight (one rAF per frame at most);
 * - pressing a `.btn` spawns a ripple from the press point.
 */
export function Interactions() {
  useEffect(() => {
    let raf = 0;
    let last: PointerEvent | null = null;
    const move = (e: PointerEvent) => {
      last = e;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const ev = last;
        const panel = (ev?.target as Element | null)?.closest?.(".panel") as HTMLElement | null;
        if (!ev || !panel) return;
        const r = panel.getBoundingClientRect();
        panel.style.setProperty("--mx", `${ev.clientX - r.left}px`);
        panel.style.setProperty("--my", `${ev.clientY - r.top}px`);
      });
    };
    const down = (e: PointerEvent) => {
      const btn = (e.target as Element | null)?.closest?.(".btn") as HTMLElement | null;
      if (!btn || (btn as HTMLButtonElement).disabled) return;
      const r = btn.getBoundingClientRect();
      const size = Math.max(r.width, r.height);
      const span = document.createElement("span");
      span.className = "ripple";
      span.style.width = span.style.height = `${size}px`;
      span.style.left = `${e.clientX - r.left - size / 2}px`;
      span.style.top = `${e.clientY - r.top - size / 2}px`;
      btn.appendChild(span);
      setTimeout(() => span.remove(), 650);
    };
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", down, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
    };
  }, []);
  return null;
}
