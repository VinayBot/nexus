"use client";

import { AnimatePresence, motion } from "motion/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useActiveMission } from "@/stores/missions";
import { useTour } from "@/stores/tour";

function useRect(id: string | null): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    if (!id) {
      setRect(null);
      return;
    }
    // one poll loop per target; it must stop when the target changes, or loops pile up
    let stopped = false;
    let scrolled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = () => {
      if (stopped) return;
      const el = document.querySelector(`[data-tour="${id}"]`);
      if (el && !scrolled) {
        scrolled = true; // bring it into view once, then let the user scroll freely
        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      setRect(el ? el.getBoundingClientRect() : null);
      timer = setTimeout(tick, 300);
    };
    tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);
  return rect;
}

/** Spotlight cut-out + caption card for guided tours, Presentation Mode and Nova. */
export function TourOverlay() {
  const { steps, index, active, autoplay, spotlight, next, prev, stop } = useTour();
  const mission = useActiveMission((s) => s.activeId);
  const router = useRouter();
  const pathname = usePathname();
  const step = active ? steps[index] : undefined;
  const route = step ? step.route.replace("{mission}", mission ?? "") : null;
  const target = step?.element ?? spotlight;
  const rect = useRect(target);

  // navigate once per step; never fight the user (or loop) when they click elsewhere
  const pushed = useRef<string | null>(null);
  useEffect(() => {
    if (!active || !route) {
      pushed.current = null;
      return;
    }
    const target = route.endsWith("/") ? route.slice(0, -1) : route;
    const key = `${index}:${target}`;
    if (pushed.current === key) return;
    pushed.current = key;
    if (pathname !== target.split("?")[0]) router.push(target);
  }, [active, index, route, pathname, router]);
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
      {/* mode="wait": the old card leaves before the next arrives (never two at once) */}
      <AnimatePresence mode="wait">
        {step && (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
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
              <button type="button" onClick={prev} disabled={index === 0} className="btn btn-ghost btn-sm">
                ← Back
              </button>
              <button type="button" onClick={next} className="btn btn-primary btn-sm">
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
