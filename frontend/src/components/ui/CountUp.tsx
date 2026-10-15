"use client";

import { animate } from "motion/react";
import { useEffect, useRef } from "react";

/**
 * Renders `value`; if it starts with a number, that number counts up from its previous value.
 * Non-numeric strings (e.g. "—") are shown as-is.
 */
export function CountUp({ value, duration = 0.9 }: { value: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(0);
  useEffect(() => {
    const el = ref.current;
    const m = /^(-?[\d,]*\.?\d+)(.*)$/.exec(value);
    if (!el) return;
    if (!m) {
      el.textContent = value;
      return;
    }
    const target = Number(m[1]!.replace(/,/g, ""));
    const decimals = (m[1]!.split(".")[1] ?? "").length;
    const suffix = m[2] ?? "";
    const ctl = animate(prev.current, target, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        el.textContent = `${v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
      },
    });
    prev.current = target;
    return () => ctl.stop();
  }, [value, duration]);
  return <span ref={ref}>{value}</span>;
}
