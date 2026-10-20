"use client";

import { Cpu, Eye, HeartPulse, History, ShieldCheck, Swords, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Robot } from "@/components/robots/Robot";
import { CountUp } from "@/components/ui/CountUp";
import { FALLBACK_AVATARS } from "@/lib/agents";
import { initialRobot, type Expression, type RobotMode } from "@/lib/robotMachine";

const FEATURES: { icon: LucideIcon; t: string; d: string; tint: string }[] = [
  {
    icon: Eye,
    t: "Watch agents think",
    d: "Every Thought, Action and Observation streams live. Robots animate only on real backend events.",
    tint: "#4fe3f0",
  },
  {
    icon: Swords,
    t: "Evidence-grounded tournaments",
    d: "Three solvers propose fixes, each patch is proven in its own sandbox, and an anonymous council judges.",
    tint: "var(--ember)",
  },
  {
    icon: ShieldCheck,
    t: "Human approval",
    d: "Risky actions pause the graph. Approve in the app or from a signed, single-use email link.",
    tint: "#34d399",
  },
  {
    icon: History,
    t: "Rewind time",
    d: "Every super-step is a SQLite checkpoint: inspect, re-run, fork with a state patch, compare branches.",
    tint: "#8b7bff",
  },
  {
    icon: HeartPulse,
    t: "Self-healing",
    d: "Trigger an incident: Hawk spots it, the squad reproduces and fixes it, verifies on live traffic and rolls back if needed.",
    tint: "var(--coral)",
  },
  {
    icon: Cpu,
    t: "All on this laptop",
    d: "Local open models through Ollama. A Resource Governor keeps a 16 GB Mac responsive.",
    tint: "var(--sun-gold)",
  },
];

export function FeatureGrid() {
  return (
    <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-2 lg:grid-cols-3">
      {FEATURES.map((f, i) => (
        <motion.div
          key={f.t}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ delay: (i % 3) * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="panel card-lift group p-6"
        >
          <span
            className="grid size-11 place-items-center rounded-xl transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6"
            style={{
              background: `linear-gradient(135deg, ${f.tint}33, ${f.tint}0d)`,
              border: `1px solid ${f.tint}66`,
              boxShadow: `0 0 24px -6px ${f.tint}`,
            }}
          >
            <f.icon className="size-5" style={{ color: f.tint }} />
          </span>
          <h3 className="mt-4 font-display text-lg font-semibold tracking-wide text-text">{f.t}</h3>
          <p className="mt-2 text-sm leading-relaxed text-muted">{f.d}</p>
        </motion.div>
      ))}
    </div>
  );
}

const FLOW = ["Intake", "Plan", "Assemble squad", "Tournament", "Approval", "Execute", "Verify", "Remember"];

/** The mission pipeline with a light pulse travelling along it. */
export function FlowStrip() {
  return (
    <div className="relative mx-auto max-w-6xl">
      <div className="absolute top-5 right-6 left-6 h-px bg-border" />
      <div className="flow-line absolute top-5 right-6 left-6 h-px opacity-80" />
      <motion.span
        className="absolute top-[14px] size-3 rounded-full bg-white shadow-[0_0_14px_4px_var(--sun-gold)]"
        animate={{ left: ["2%", "97%"] }}
        transition={{ repeat: Infinity, duration: 5, ease: "easeInOut", repeatDelay: 0.6 }}
      />
      <ol className="relative grid grid-cols-4 gap-y-6 md:grid-cols-8">
        {FLOW.map((s, i) => (
          <motion.li
            key={s}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.07 }}
            className="flex flex-col items-center gap-2 text-center"
          >
            <span className="grid size-10 place-items-center rounded-full border border-border-strong bg-[var(--lacquer)] font-mono text-xs text-gold shadow-[0_0_18px_-6px_var(--sun-gold)]">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="text-xs text-muted">{s}</span>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}

export function StatsStrip({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="glass mx-auto grid max-w-3xl grid-cols-2 divide-x divide-border/60 md:grid-cols-4">
      {items.map((s) => (
        <div key={s.label} className="px-5 py-3 text-center">
          <p className="font-display text-2xl font-bold text-text">
            <CountUp value={s.value} duration={1.6} />
          </p>
          <p className="mt-0.5 text-[10px] tracking-[0.2em] text-faint uppercase">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

/** Decorative squad line-up: each robot cycles through a few of its moves. */
const SHOWCASE: { id: string; moves: [RobotMode, Expression][] }[] = [
  {
    id: "sage",
    moves: [
      ["thinking", "thinking"],
      ["idle", "normal"],
      ["handoff", "happy"],
    ],
  },
  {
    id: "blaze",
    moves: [
      ["debating", "focused"],
      ["success", "happy"],
      ["idle", "normal"],
    ],
  },
  {
    id: "aegis",
    moves: [
      ["testing", "focused"],
      ["idle", "normal"],
      ["waving", "happy"],
    ],
  },
  {
    id: "volt",
    moves: [
      ["using_tool", "focused"],
      ["idle", "normal"],
      ["retrying", "confused"],
    ],
  },
];

export function Showcase({ className }: { className?: string }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 2600);
    return () => clearInterval(t);
  }, []);
  return (
    <div className={className}>
      {SHOWCASE.map((r, i) => {
        const [mode, expression] = r.moves[(tick + i) % r.moves.length]!;
        return (
          <motion.div
            key={r.id}
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.6 + i * 0.15, duration: 0.7 }}
          >
            <Robot
              avatar={FALLBACK_AVATARS[r.id]!}
              state={{ ...initialRobot(0), mode, expression }}
              size={74}
              showBubble={false}
              label={r.id}
            />
          </motion.div>
        );
      })}
    </div>
  );
}
