import { create } from "zustand";
import type { NexusEvent, PayloadOf } from "@/lib/events";
import type { SocketStatus } from "@/lib/ws";

export interface TickerItem {
  id: string;
  ts: number;
  type: string;
  missionId: string | null;
  text: string;
}

interface LiveState {
  socket: SocketStatus;
  governor: PayloadOf<"governor.metrics"> | null;
  governorHistory: { ts: number; ram: number; tps: number; queue: number }[];
  health: PayloadOf<"service.health"> | null;
  healthHistory: { ts: number; status: string; errorRate: number }[];
  ticker: TickerItem[];
  circuits: Record<string, PayloadOf<"circuit.state">>;
  setSocket: (s: SocketStatus) => void;
  ingest: (e: NexusEvent) => void;
}

function describe(e: NexusEvent): string | null {
  switch (e.type) {
    case "mission.created":
      return `New mission: ${e.payload.title}`;
    case "mission.completed":
      return `Mission ${e.payload.outcome}: ${e.payload.summary}`;
    case "mission.failed":
      return `Mission failed: ${e.payload.error.slice(0, 90)}`;
    case "interrupt.raised":
      return `Approval needed: ${e.payload.summary}`;
    case "interrupt.resolved":
      return `Human ${e.payload.decision}d via ${e.payload.channel}`;
    case "incident.detected":
      return `Incident ${e.payload.incident_id}: ${e.payload.signal}`;
    case "chaos.toggled":
      return `Chaos ${e.payload.switch} ${e.payload.enabled ? "rung" : "silenced"}`;
    case "email.sent":
      return `Email ${e.payload.status}: ${e.payload.subject}`;
    default:
      return null;
  }
}

/** Global, cross-mission live data fed by /ws/global. */
export const useLive = create<LiveState>()((set) => ({
  socket: "connecting",
  governor: null,
  governorHistory: [],
  health: null,
  healthHistory: [],
  ticker: [],
  circuits: {},
  setSocket: (socket) => set({ socket }),
  ingest: (e) =>
    set((s) => {
      if (e.type === "governor.metrics") {
        const point = {
          ts: e.ts,
          ram: e.payload.ram_percent,
          tps: e.payload.tokens_per_sec,
          queue: e.payload.queue_depth,
        };
        return { governor: e.payload, governorHistory: [...s.governorHistory.slice(-299), point] };
      }
      if (e.type === "service.health") {
        const point = { ts: e.ts, status: e.payload.status, errorRate: e.payload.error_rate };
        return { health: e.payload, healthHistory: [...s.healthHistory.slice(-179), point] };
      }
      if (e.type === "circuit.state") {
        return { circuits: { ...s.circuits, [e.payload.key]: e.payload } };
      }
      const text = describe(e);
      if (!text) return {};
      return {
        ticker: [...s.ticker.slice(-49), { id: e.id, ts: e.ts, type: e.type, missionId: e.mission_id ?? null, text }],
      };
    }),
}));
