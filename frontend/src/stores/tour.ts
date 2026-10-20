import { create } from "zustand";

export interface TourStep {
  /** Route to open; `{mission}` is replaced by the active mission id. */
  route: string;
  /** `data-tour` id of the element to spotlight. */
  element: string;
  title: string;
  body: string;
}

/** The main tour: one stop per screen, in the order of docs/HOW_IT_WORKS.md. */
export const MAIN_TOUR: TourStep[] = [
  {
    route: "/missions",
    element: "new-mission",
    title: "Start a mission",
    body: "Type what you want and press Start. Pick a type (web page, question, new ticket…) or leave Auto. Add “…and email the result to name@example.com” to get it by email.",
  },
  {
    route: "/missions",
    element: "thought-stream",
    title: "Activity",
    body: "Every step the agents take, live: the plan, who got which job, tool calls, checks and the risk score. “Key steps” hides the low-level routing.",
  },
  {
    route: "/missions",
    element: "mission-floor",
    title: "Agents at work",
    body: "The robots move only when the backend reports real work: data orbs fly on handoffs, beams on tool calls, light bars on tests. “Graph” shows the same mission as a LangGraph.",
  },
  {
    route: "/missions",
    element: "system-power",
    title: "System power",
    body: "Free memory, the loaded local models and tokens per second. Under memory pressure NEXUS slows down instead of crashing.",
  },
  {
    route: "/approvals",
    element: "approvals-list",
    title: "Approvals",
    body: "Risky actions pause and wait for you. Decide here, in the pop-up on any screen, or from an email link. Every decision is logged.",
  },
  {
    route: "/graph/{mission}",
    element: "live-graph",
    title: "Live graph",
    body: "The real agent graph: glowing nodes are running, light flows along the branch just taken, and ×N counts loops.",
  },
  {
    route: "/arena/{mission}",
    element: "arena",
    title: "Arena",
    body: "For questions and fixes, three agents answer independently, review each other anonymously, and a judge picks the best with evidence.",
  },
  {
    route: "/timetravel/{mission}",
    element: "fork-button",
    title: "Time travel",
    body: "Every step is saved. Re-run from any point, fork with a change, or try the runner-up answer.",
  },
  {
    route: "/chaos",
    element: "chaos-switches",
    title: "Chaos Lab",
    body: "Switch on a bug in the demo shop. Hawk notices within seconds and the team fixes it, tests it and asks you before applying.",
  },
  {
    route: "/memory",
    element: "vessels",
    title: "Memory",
    body: "What the agents remember: past missions, documents and the Fix Library that makes a repeated bug fast to fix.",
  },
  {
    route: "/tools",
    element: "tools-grid",
    title: "Tools",
    body: "The seven tool servers the agents can use, each agent with its own allowlist. Files are locked to the mission's own folder.",
  },
  {
    route: "/insights",
    element: "traces",
    title: "Insights",
    body: "Traces, token use, retries and honest benchmark results for every mission.",
  },
  {
    route: "/settings",
    element: "models",
    title: "Models",
    body: "Switch between Lite, Balanced and Standard local models with one click. Old models are unloaded to free memory.",
  },
  {
    route: "/settings",
    element: "email-results",
    title: "Email results",
    body: "Sign in with Google once; results are then emailed from your account whenever a prompt asks for it.",
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
