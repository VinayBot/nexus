"use client";

import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  life: number;
  petal: boolean;
  spin: number;
}

interface EmbersProps {
  /** Hard cap; the canvas never holds more particles than this. */
  max?: number;
  /** Fraction of particles drawn as cherry petals instead of embers. */
  petals?: number;
  className?: string;
}

/**
 * Drifting embers and cherry petals on a single canvas. Pauses when the tab is
 * hidden or the element is offscreen, and renders nothing under reduced motion.
 */
export function Embers({ max = 40, petals = 0.25, className }: EmbersProps) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const spawn = (anywhere: boolean): Particle => ({
      x: Math.random() * w,
      y: anywhere ? Math.random() * h : h + 10,
      vx: (Math.random() - 0.3) * 0.35,
      vy: -(0.15 + Math.random() * 0.45),
      r: 0.8 + Math.random() * 2.2,
      life: 1,
      petal: Math.random() < petals,
      spin: Math.random() * Math.PI,
    });
    const ps: Particle[] = Array.from({ length: max }, () => spawn(true));

    let visible = true;
    const io = new IntersectionObserver(([e]) => (visible = e?.isIntersecting ?? true));
    io.observe(canvas);

    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (!visible || document.hidden) return;
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < ps.length; i++) {
        const p = ps[i]!;
        p.x += p.vx + Math.sin(p.y * 0.01) * 0.15;
        p.y += p.petal ? -p.vy * 0.6 : p.vy;
        p.spin += 0.02;
        p.life -= 0.0012;
        if (p.y < -10 || p.y > h + 20 || p.life <= 0) ps[i] = spawn(false);
        if (p.petal) {
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.spin);
          ctx.fillStyle = `rgba(255, 196, 206, ${0.55 * p.life})`;
          ctx.beginPath();
          ctx.ellipse(0, 0, p.r * 2.2, p.r * 1.1, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        } else {
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 3);
          g.addColorStop(0, `rgba(255, 208, 138, ${0.9 * p.life})`);
          g.addColorStop(1, "rgba(242, 102, 42, 0)");
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r * 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
    };
  }, [max, petals]);

  return <canvas ref={ref} className={className} aria-hidden />;
}
