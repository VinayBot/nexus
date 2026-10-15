"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, Play } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogoMark, Wordmark } from "@/components/brand/Logo";
import { FeatureGrid, FlowStrip, Showcase, StatsStrip } from "@/components/landing/Sections";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { HoloCore } from "@/components/landing/HoloCore";
import { AppBackdrop } from "@/components/scenery/AppBackdrop";
import { FALLBACK_AVATARS } from "@/lib/agents";
import { get } from "@/lib/api";
import { initialRobot } from "@/lib/robotMachine";
import { useTour } from "@/stores/tour";
import { useUi } from "@/stores/ui";

const TAGLINE =
  "Mission control for a squad of AI agents — local models, real tools, human approvals, rewindable time.";

/** Types the tagline out once, like a terminal boot line. */
function useTyped(text: string, delay = 900, speed = 22) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let i = 0;
    let t: ReturnType<typeof setTimeout> = setTimeout(function tick() {
      i += 1;
      setN(i);
      if (i < text.length) t = setTimeout(tick, speed);
    }, delay);
    return () => clearTimeout(t);
  }, [text, delay, speed]);
  return text.slice(0, n);
}

function ReadyDot({ status }: { status?: string }) {
  const color = status === "ok" ? "var(--jade)" : status ? "var(--amber)" : "var(--danger)";
  return (
    <span className="relative flex size-2">
      {status === "ok" && <span className="absolute inset-0 animate-ping rounded-full" style={{ background: color }} />}
      <span className="relative size-2 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
    </span>
  );
}

export default function Gate() {
  const router = useRouter();
  const perf = useUi((s) => s.performanceMode);
  const [slash, setSlash] = useState(false);
  const [mode, setMode] = useState<"idle" | "waving">("idle");
  const typed = useTyped(TAGLINE);
  const stats = useQuery({
    queryKey: ["gate-stats"],
    queryFn: () =>
      get<{ missions: { status: string; calls: number; prompt: number; completion: number }[] }>(
        "/observability/summary?limit=50",
      ),
    retry: false,
  });
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: () => get<{ status: string }>("/health/ready"),
    retry: false,
  });
  useEffect(() => {
    const t = setTimeout(() => setMode("waving"), 1400);
    const u = setTimeout(() => setMode("idle"), 4800);
    return () => {
      clearTimeout(t);
      clearTimeout(u);
    };
  }, []);
  const enter = (tour = false) => {
    setSlash(true);
    setTimeout(() => {
      router.push("/missions");
      if (tour) useTour.getState().start(undefined, true);
    }, 650);
  };
  const missions = stats.data?.missions ?? [];
  const calls = missions.reduce((a, m) => a + m.calls, 0);
  const tokens = missions.reduce((a, m) => a + (m.prompt ?? 0) + (m.completion ?? 0), 0);
  const backend = ready.data?.status;

  return (
    <main className="relative min-h-dvh overflow-x-hidden">
      <RobotDefs />
      <section className="relative h-dvh min-h-[640px]">
        <AppBackdrop />
        <HoloCore className="pointer-events-none absolute top-1/2 left-1/2 h-[min(92vh,900px)] w-[min(92vh,900px)] -translate-x-1/2 -translate-y-[54%] opacity-90" />

        {/* top bar */}
        <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-6 py-5 md:px-10">
          <div className="flex items-center gap-3">
            <LogoMark size={34} />
            <Wordmark className="text-lg" />
          </div>
          <div className="flex items-center gap-3">
            <span className="chip hidden bg-black/40 sm:inline-flex">
              <ReadyDot status={backend} />
              {backend === "ok" ? "Systems online" : backend ? `Systems ${backend}` : "Backend offline"}
            </span>
            <button type="button" onClick={() => enter()} className="btn btn-ghost btn-sm">
              Open app <ArrowRight className="size-3.5" />
            </button>
          </div>
        </header>

        {!perf && (
          <Showcase className="pointer-events-none absolute bottom-[19%] left-[5%] z-10 hidden items-end gap-1 xl:flex" />
        )}
        <div className="pointer-events-none absolute right-[9%] bottom-[20%] z-10 hidden lg:block">
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.9, delay: 0.4 }}
          >
            <Robot
              avatar={FALLBACK_AVATARS.commander!}
              state={{ ...initialRobot(0), mode, expression: mode === "waving" ? "happy" : "normal" }}
              isCommander
              size={120}
              showBubble={false}
              label="Commander"
            />
          </motion.div>
        </div>

        <div className="relative z-10 grid h-full place-items-center px-6 text-center">
          <div className="-mt-10 max-w-3xl">
            <motion.span
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="chip mx-auto border-[rgb(79_227_240/0.4)] bg-black/40 px-3 py-1 font-mono text-[10px] tracking-[0.25em] text-[var(--cyan)] uppercase"
            >
              <span className="size-1.5 rotate-45 bg-[var(--cyan)] shadow-[0_0_8px_var(--cyan)]" />
              LangGraph · Ollama · 14 agents · 100% local
            </motion.span>
            <h1 className="mt-6 font-display text-7xl font-bold tracking-[0.18em] md:text-9xl" aria-label="NEXUS">
              {"NEXUS".split("").map((ch, i) => (
                <motion.span
                  key={i}
                  aria-hidden
                  className="inline-block bg-gradient-to-b from-[#fff4dd] via-[#ffc66b] to-[#ff6b3d] bg-clip-text text-transparent drop-shadow-[0_0_28px_rgba(255,140,60,0.55)]"
                  initial={{ opacity: 0, y: 60, rotateX: -90, filter: "blur(12px)" }}
                  animate={{ opacity: 1, y: 0, rotateX: 0, filter: "blur(0px)" }}
                  transition={{ delay: 0.25 + i * 0.09, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                >
                  {ch}
                </motion.span>
              ))}
            </h1>
            <p className="mx-auto mt-5 min-h-[3.5rem] max-w-2xl text-lg leading-relaxed text-[#fff3e6] [text-shadow:0_1px_10px_rgba(5,6,11,0.95)] md:text-xl">
              {typed}
              <span className="ml-0.5 inline-block h-5 w-[2px] translate-y-1 animate-pulse bg-[var(--sun-gold)]" />
            </p>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.1, duration: 0.6 }}
              className="mt-9 flex flex-wrap items-center justify-center gap-3"
            >
              <button type="button" onClick={() => enter()} className="btn btn-primary btn-lg glow-pulse">
                Enter Command Center <ArrowRight className="size-4" />
              </button>
              <button type="button" onClick={() => enter(true)} className="btn btn-ghost btn-lg bg-black/30">
                <Play className="size-4" /> Watch the tour
              </button>
            </motion.div>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.4 }}
          className="absolute inset-x-0 bottom-14 z-10 px-6"
        >
          <StatsStrip
            items={[
              { label: "Missions", value: String(missions.length) },
              { label: "Local LLM calls", value: String(calls) },
              { label: "Tokens", value: String(tokens) },
              { label: "Cloud spend", value: "$0" },
            ]}
          />
        </motion.div>
        <ChevronDown
          className="absolute bottom-4 left-1/2 z-10 size-5 -translate-x-1/2 animate-bounce text-faint"
          aria-hidden
        />
      </section>

      <section className="relative z-10 px-6 py-20">
        <p className="kicker mx-auto mb-3 flex w-fit">How a mission flows</p>
        <h2 className="mb-12 text-center font-display text-3xl font-bold tracking-wide md:text-4xl">
          <span className="title-gradient">From a sentence to a verified fix</span>
        </h2>
        <FlowStrip />
      </section>

      <section className="relative z-10 px-6 pb-24">
        <p className="kicker mx-auto mb-3 flex w-fit">Capabilities</p>
        <h2 className="mb-12 text-center font-display text-3xl font-bold tracking-wide md:text-4xl">
          <span className="title-gradient">Everything visible, everything real</span>
        </h2>
        <FeatureGrid />
        <div className="mt-14 flex justify-center">
          <button type="button" onClick={() => enter()} className="btn btn-primary btn-lg">
            Launch NEXUS <ArrowRight className="size-4" />
          </button>
        </div>
      </section>

      <AnimatePresence>
        {slash && (
          <>
            <motion.div
              className="fixed inset-0 z-50 bg-[var(--bg)]"
              initial={{ clipPath: "circle(0% at 50% 50%)" }}
              animate={{ clipPath: "circle(150% at 50% 50%)" }}
              transition={{ duration: 0.6, ease: [0.65, 0, 0.35, 1] }}
            />
            <motion.div
              className="fixed top-1/2 left-1/2 z-50 size-24 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--sun-gold)]"
              initial={{ scale: 0.2, opacity: 1 }}
              animate={{ scale: 14, opacity: 0 }}
              transition={{ duration: 0.65, ease: "easeOut" }}
            />
          </>
        )}
      </AnimatePresence>
    </main>
  );
}
