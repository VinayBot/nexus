"use client";

import { AnimatePresence, motion } from "motion/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useActiveMission } from "@/stores/missions";
import { useTour } from "@/stores/tour";

function useRect(id: string | null): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    if (!id) {
      setRect(null);
      return;
    }
    let raf = 0;
    const tick = () => {
      const el = document.querySelector(`[data-tour="${id}"]`);
      setRect(el ? el.getBoundingClientRect() : null);
      raf = requestAnimationFrame(() => setTimeout(tick, 250));
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [id]);
  return rect;
}

/** Spotlight cut-out + caption card for guided tours, Presentation Mode and Hikari. */
export function TourOverlay() {
  const { steps, index, active, autoplay, spotlight, next, prev, stop } = useTour();
  const mission = useActiveMission((s) => s.activeId);
  const router = useRouter();
  const pathname = usePathname();
  const step = active ? steps[index] : undefined;
  const route = step ? step.route.replace("{mission}", mission ?? "") : null;
  const target = step?.element ?? spotlight;
  const rect = useRect(target);

  useEffect(() => {
    if (route && pathname !== route.replace(/\/$/, "")) router.push(route.endsWith("/") ? route.slice(0, -1) : route);
  }, [route, pathname, router]);
  useEffect(() => {
    if (!active || !autoplay) return;
    const t = setTimeout(next, 8000);
    return () => clearTimeout(t);
  }, [active, autoplay, index, next]);
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") stop();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, next, prev, stop]);

  if (!target) return null;
  const pad = 8;
  return (
    <div className="pointer-events-none fixed inset-0 z-[60]" aria-live="polite">
      {rect && (
        <motion.div
          className="absolute rounded-2xl border-2 border-accent"
          animate={{
            left: rect.left - pad,
            top: rect.top - pad,
            width: rect.width + pad * 2,
            height: rect.height + pad * 2,
          }}
          transition={{ type: "spring", stiffness: 160, damping: 22 }}
          style={{
            boxShadow: active ? "0 0 0 9999px rgba(10,4,4,0.62), 0 0 30px var(--cyan)" : "0 0 30px var(--cyan)",
          }}
        />
      )}
      <AnimatePresence>
        {step && (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="panel pointer-events-auto absolute bottom-8 left-1/2 w-[min(560px,92vw)] -translate-x-1/2 p-4"
            role="dialog"
            aria-label="Guided tour"
          >
            <p className="text-[11px] text-faint">
              {autoplay ? "Presentation mode" : "Guided tour"} · {index + 1} / {steps.length}
            </p>
            <h3 className="font-display text-lg text-gold">{step.title}</h3>
            <p className="mt-1 text-sm text-text">{step.body}</p>
            {!rect && <p className="mt-1 text-[11px] text-faint">(open a mission first to see this part live)</p>}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={prev}
                disabled={index === 0}
                className="chip cursor-pointer disabled:opacity-40"
              >
                ← Back
              </button>
              <button type="button" onClick={next} className="chip cursor-pointer border-accent text-accent">
                {index + 1 === steps.length ? "Finish" : "Next →"}
              </button>
              <button type="button" onClick={stop} className="chip ml-auto cursor-pointer">
                Exit (Esc)
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
