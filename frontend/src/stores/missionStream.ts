"use client";

import { useEffect, useState } from "react";
import { create } from "zustand";
import type { NexusEvent } from "@/lib/events";
import { emptyView, reduceMission, type MissionView } from "@/lib/missionView";
import { settle } from "@/lib/robotMachine";
import { EventSocket, type SocketStatus } from "@/lib/ws";

interface StreamState {
  views: Record<string, MissionView>;
  events: Record<string, NexusEvent[]>;
  status: Record<string, SocketStatus>;
  apply: (missionId: string, e: NexusEvent) => void;
  setStatus: (missionId: string, s: SocketStatus) => void;
  reset: (missionId: string) => void;
}

const MAX_EVENTS = 6000;

export const useStreams = create<StreamState>()((set) => ({
  views: {},
  events: {},
  status: {},
  apply: (id, e) =>
    set((s) => {
      const view = reduceMission(s.views[id] ?? emptyView(id), e);
      if (view === s.views[id]) return {};
      const list = s.events[id] ?? [];
      return {
        views: { ...s.views, [id]: view },
        events: { ...s.events, [id]: list.length >= MAX_EVENTS ? [...list.slice(-MAX_EVENTS + 1), e] : [...list, e] },
      };
    }),
  setStatus: (id, st) => set((s) => ({ status: { ...s.status, [id]: st } })),
  reset: (id) => set((s) => ({ views: { ...s.views, [id]: emptyView(id) }, events: { ...s.events, [id]: [] } })),
}));

const sockets = new Map<string, { socket: EventSocket; refs: number }>();

/** Subscribe to a mission's live event stream (shared socket, ref-counted). */
export function useMissionStream(missionId: string | null | undefined): MissionView {
  const view = useStreams((s) => (missionId ? s.views[missionId] : undefined));
  useEffect(() => {
    if (!missionId) return;
    let entry = sockets.get(missionId);
    if (!entry) {
      const { apply, setStatus, views } = useStreams.getState();
      const socket = new EventSocket({
        missionId,
        onEvent: (e) => apply(missionId, e),
        onStatus: (st) => setStatus(missionId, st),
      });
      socket.start(views[missionId]?.lastSeq ?? 0);
      entry = { socket, refs: 0 };
      sockets.set(missionId, entry);
    }
    entry.refs += 1;
    return () => {
      const e = sockets.get(missionId);
      if (!e) return;
      e.refs -= 1;
      if (e.refs <= 0) {
        e.socket.stop();
        sockets.delete(missionId);
      }
    };
  }, [missionId]);
  return view ?? emptyView(missionId ?? null);
}

/** Re-render every `ms` so time-based robot decay (celebration → idle → sleep) shows. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

export { settle };
