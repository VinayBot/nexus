"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { SkyBackdrop } from "@/components/scenery/SkyBackdrop";
import { FALLBACK_AVATARS } from "@/lib/agents";
import { get } from "@/lib/api";
import { initialRobot } from "@/lib/robotMachine";
import { useUi } from "@/stores/ui";

const HeroScene = dynamic(() => import("@/components/landing/HeroScene"), { ssr: false });

const FEATURES = [
  {
    t: "Watch agents think",
    d: "Every Thought, Action and Observation streams live; robots animate only on real backend events.",
  },
  {
    t: "Evidence-grounded tournaments",
    d: "Three Ronin propose fixes, each patch is proven in its own sandbox, an anonymous council judges.",
  },
  { t: "Human seal", d: "Risky actions pause the graph. Approve in the app or from a signed, single-use email link." },
  {
    t: "Rewind time",
    d: "Every super-step is a SQLite checkpoint: inspect, re-run, fork with a state patch, compare branches.",
  },
  {
    t: "Self-healing",
    d: "Ring a chaos bell: Kuro spots the incident, the clan reproduces, fixes, verifies on live traffic, rolls back if needed.",
  },
  { t: "All on this laptop", d: "Local open models through Ollama; a Resource Governor keeps a 16 GB Mac responsive." },
];

export default function Gate() {
  const router = useRouter();
  const perf = useUi((s) => s.performanceMode);
  const [slash, setSlash] = useState(false);
  const [mode, setMode] = useState<"idle" | "waving">("idle");
  const stats = useQuery({
    queryKey: ["gate-stats"],
    queryFn: () => get<{ missions: { status: string; calls: number }[] }>("/observability/summary?limit=50"),
    retry: false,
  });
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: () => get<{ status: string }>("/health/ready"),
    retry: false,
  });
  useEffect(() => {
    const t = setTimeout(() => setMode("waving"), 900);
    const u = setTimeout(() => setMode("idle"), 4200);
    return () => {
      clearTimeout(t);
      clearTimeout(u);
    };
  }, []);
  const enter = () => {
    setSlash(true);
    setTimeout(() => router.push("/dojo"), 650);
  };
  const missions = stats.data?.missions ?? [];

  return (
    <main className="relative min-h-dvh overflow-x-hidden">
      <RobotDefs />
      <section className="relative h-dvh">
        <div
          className="absolute inset-0 -z-10"
          style={{ background: "linear-gradient(180deg,#3b0a0a 0%,#8e1b17 40%,#c8341f 62%,#f2662a 78%,#140909 100%)" }}
        />
        {perf ? (
          <SkyBackdrop />
        ) : (
          <div className="absolute inset-0">
            <HeroScene />
          </div>
        )}
        <div className="pointer-events-none absolute right-[19%] bottom-[24%] z-10 hidden md:block">
          <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8 }}>
            <Robot
              avatar={FALLBACK_AVATARS.shogun!}
              state={{ ...initialRobot(0), mode, expression: mode === "waving" ? "happy" : "normal" }}
              isShogun
              size={110}
              showBubble={false}
            />
          </motion.div>
        </div>
        <div className="relative z-10 grid h-full place-items-center px-6 text-center">
          <div className="rounded-3xl bg-[radial-gradient(ellipse_at_center,rgba(20,9,9,0.55),transparent_70%)] px-10 py-8">
            <motion.h1
              initial={{ opacity: 0, letterSpacing: "0.6em" }}
              animate={{ opacity: 1, letterSpacing: "0.3em" }}
              transition={{ duration: 1.4 }}
              className="font-display text-6xl font-extrabold text-[var(--sun-core)] drop-shadow-[0_0_30px_rgba(247,164,64,0.6)] md:text-8xl"
            >
              NEXUS
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="mt-4 text-lg text-[#fff3e6] [text-shadow:0_1px_8px_rgba(20,9,9,0.9)]"
            >
              A dynamic multi-agent dojo — local models, real tools, human seals, rewindable time.
            </motion.p>
            <motion.button
              type="button"
              onClick={enter}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
              whileHover={{ scale: 1.04 }}
              className="mt-8 rounded-full border border-[var(--sun-gold)]/70 bg-black/40 px-9 py-3 font-display text-lg text-white shadow-[var(--glow-gold)] backdrop-blur"
            >
              Enter the Dojo
            </motion.button>
          </div>
        </div>
        <div className="absolute inset-x-0 bottom-4 z-10 flex justify-center gap-3 text-xs text-[#f6ebe0]/80">
          <span className="chip bg-black/40">
            {ready.data?.status === "ok"
              ? "● backend ready"
              : ready.data
                ? `● ${ready.data.status}`
                : "● backend offline"}
          </span>
          <span className="chip bg-black/40">{missions.length} missions</span>
          <span className="chip bg-black/40">
            {missions.reduce((a, m) => a + m.calls, 0).toLocaleString()} local LLM calls
          </span>
          <span className="chip bg-black/40">$0 cloud spend</span>
        </div>
      </section>
      <section className="relative z-10 bg-[var(--ink)] px-6 py-16">
        <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.t}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="panel p-5"
            >
              <h3 className="font-display text-lg text-gold">{f.t}</h3>
              <p className="mt-2 text-sm text-muted">{f.d}</p>
            </motion.div>
          ))}
        </div>
      </section>
      <AnimatePresence>
        {slash && (
          <>
            <motion.div
              className="fixed inset-0 z-50 bg-[var(--ink)]"
              initial={{ clipPath: "polygon(0 0, 0 0, 0 100%, 0 100%)" }}
              animate={{ clipPath: "polygon(0 0, 130% 0, 100% 100%, -30% 100%)" }}
              transition={{ duration: 0.55, ease: "easeIn" }}
            />
            <motion.div
              className="fixed top-1/2 left-0 z-50 h-0.5 w-[140%] origin-left bg-white shadow-[0_0_20px_white]"
              initial={{ rotate: -18, scaleX: 0, x: "-10%" }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.25 }}
            />
          </>
        )}
      </AnimatePresence>
    </main>
  );
}
