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
    route: "/missions",
    element: "mission-floor",
    title: "The Mission Floor",
    body: "Every robot here moves only when the backend emits a real event: data orbs fly on handoffs, beams on MCP tool calls, light bars on sandbox tests.",
  },
  {
    route: "/missions",
    element: "thought-stream",
    title: "Thought Stream",
    body: "The live ReAct trace — Thought, Action (MCP tool), Observation — plus routing, retries, verdicts and guardrails.",
  },
  {
    route: "/missions",
    element: "system-power",
    title: "System Power",
    body: "The Resource Governor: RAM, loaded local models, queue depth and tokens/sec. Under memory pressure it lowers concurrency instead of failing.",
  },
  {
    route: "/learn?tab=curriculum",
    element: "curriculum",
    title: "Curriculum Map",
    body: "Every Day 16–20 concept, where it lives in code, and a live count of the real events proving it ran.",
  },
  {
    route: "/chaos",
    element: "chaos-switches",
    title: "Chaos Lab",
    body: "Arm a chaos switch to inject a real bug into the live demo-service. Hawk notices within seconds and opens an incident.",
  },
  {
    route: "/graph/{mission}",
    element: "live-graph",
    title: "Live Graph",
    body: "The compiled LangGraph itself: glowing nodes are running, light flows along the branch just taken, ×N counts cycle iterations.",
  },
  {
    route: "/arena/{mission}",
    element: "arena",
    title: "Arena",
    body: "Three Challengers propose independently, patches are proven in sandboxes, masks drop for anonymous review, and Arbiter weighs evidence first.",
  },
  {
    route: "/approvals",
    element: "approvals-list",
    title: "Approvals",
    body: "Risky actions pause the graph with interrupt(). Approve here or from the signed email link — either resumes it with Command(resume=…).",
  },
  {
    route: "/timetravel/{mission}",
    element: "fork-button",
    title: "Time Travel",
    body: "Every super-step is a SQLite checkpoint. Re-run from any of them, fork with a state patch, or choose the tournament runner-up.",
  },
  {
    route: "/memory",
    element: "vessels",
    title: "Memory",
    body: "Context windows pruned by sliding window or rolling summary, and the long-term library — including the Fix Library that makes repeat incidents fast.",
  },
  {
    route: "/tools",
    element: "tools-grid",
    title: "Tools",
    body: "Seven MCP servers with per-agent allowlists, a path jail, and a system-only email server so nothing is sent without approval.",
  },
  {
    route: "/insights",
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
