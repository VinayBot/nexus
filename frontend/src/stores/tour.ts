import { create } from "zustand";

export interface TourStep {
  /** Route to open; `{mission}` is replaced by the active mission id. */
  route: string;
  /** `data-tour` id of the element to spotlight. */
  element: string;
  title: string;
  body: string;
}

/** The main tour mirrors docs/DEMO_SCRIPT.md. */
export const MAIN_TOUR: TourStep[] = [
  {
    route: "/dojo",
    element: "dojo-floor",
    title: "The Dojo Floor",
    body: "Every robot here moves only when the backend emits a real event: scrolls fly on handoffs, beams on MCP tool calls, lanterns on sandbox tests.",
  },
  {
    route: "/dojo",
    element: "thought-stream",
    title: "Thought Stream",
    body: "The live ReAct trace — Thought, Action (MCP tool), Observation — plus routing, retries, verdicts and guardrails.",
  },
  {
    route: "/dojo",
    element: "dojo-power",
    title: "Dojo Power",
    body: "The Resource Governor: RAM, loaded local models, queue depth and tokens/sec. Under memory pressure it lowers concurrency instead of failing.",
  },
  {
    route: "/curriculum",
    element: "curriculum",
    title: "Curriculum Map",
    body: "Every Day 16–20 concept, where it lives in code, and a live count of the real events proving it ran.",
  },
  {
    route: "/shrine",
    element: "bells",
    title: "Chaos Shrine",
    body: "Ring a bell to inject a real bug into the live demo-service. Kuro notices within seconds and opens an incident.",
  },
  {
    route: "/graph/{mission}",
    element: "live-graph",
    title: "Live Graph",
    body: "The compiled LangGraph itself: lit lanterns are running nodes, light flows along the branch just taken, ×N counts cycle iterations.",
  },
  {
    route: "/arena/{mission}",
    element: "arena",
    title: "Council Arena",
    body: "Three Ronin propose independently, patches are proven in sandboxes, masks drop for anonymous review, and Hakari weighs evidence first.",
  },
  {
    route: "/approvals",
    element: "approvals-list",
    title: "Shogun's Seal",
    body: "Risky actions pause the graph with interrupt(). Approve here or from the signed email link — either resumes it with Command(resume=…).",
  },
  {
    route: "/timetravel/{mission}",
    element: "fork-button",
    title: "Scroll of Time",
    body: "Every super-step is a SQLite checkpoint. Re-run from any of them, fork with a state patch, or choose the tournament runner-up.",
  },
  {
    route: "/memory",
    element: "vessels",
    title: "Memory Palace",
    body: "Context windows pruned by sliding window or rolling summary, and the long-term library — including the Fix Library that makes repeat incidents fast.",
  },
  {
    route: "/armory",
    element: "armory",
    title: "Armory",
    body: "Seven MCP servers with per-agent allowlists, a path jail, and a system-only email server so nothing is sent without approval.",
  },
  {
    route: "/observatory",
    element: "traces",
    title: "Observatory",
    body: "OpenTelemetry traces per mission, token usage by purpose, retries absorbed, circuit breakers and routing decisions.",
  },
];

interface TourState {
  steps: TourStep[];
  index: number;
  active: boolean;
  autoplay: boolean;
  spotlight: string | null;
  start: (steps?: TourStep[], autoplay?: boolean) => void;
  next: () => void;
  prev: () => void;
  stop: () => void;
  flash: (element: string) => void;
}

export const useTour = create<TourState>()((set, get) => ({
  steps: MAIN_TOUR,
  index: 0,
  active: false,
  autoplay: false,
  spotlight: null,
  start: (steps = MAIN_TOUR, autoplay = false) => set({ steps, index: 0, active: true, autoplay }),
  next: () => {
    const { index, steps } = get();
    if (index + 1 >= steps.length) set({ active: false, autoplay: false });
    else set({ index: index + 1 });
  },
  prev: () => set((s) => ({ index: Math.max(0, s.index - 1) })),
  stop: () => set({ active: false, autoplay: false }),
  flash: (element) => {
    set({ spotlight: element });
    setTimeout(() => get().spotlight === element && set({ spotlight: null }), 5000);
  },
}));
