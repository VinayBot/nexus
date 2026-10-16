"use client";

import { useEffect, useState } from "react";
import { create } from "zustand";
import { get } from "@/lib/api";
import type { NexusEvent } from "@/lib/events";
import { emptyView, reduceMission, type MissionView } from "@/lib/missionView";
import { settle } from "@/lib/robotMachine";
import { EventSocket, type SocketStatus } from "@/lib/ws";

interface StreamState {
  views: Record<string, MissionView>;
  events: Record<string, NexusEvent[]>;
  status: Record<string, SocketStatus>;
  apply: (missionId: string, e: NexusEvent) => void;
  /** Apply a batch of events with a single store update (one re-render). */
  applyMany: (missionId: string, es: NexusEvent[]) => void;
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
  applyMany: (id, es) =>
    set((s) => {
      if (!es.length) return {};
      let view = s.views[id] ?? emptyView(id);
      const accepted: NexusEvent[] = [];
      for (const e of es) {
        const next = reduceMission(view, e);
        if (next !== view) {
          view = next;
          accepted.push(e);
        }
      }
      if (!accepted.length) return {};
      const list = [...(s.events[id] ?? []), ...accepted].slice(-MAX_EVENTS);
      return { views: { ...s.views, [id]: view }, events: { ...s.events, [id]: list } };
    }),
  setStatus: (id, st) => set((s) => ({ status: { ...s.status, [id]: st } })),
  reset: (id) => set((s) => ({ views: { ...s.views, [id]: emptyView(id) }, events: { ...s.events, [id]: [] } })),
}));

const sockets = new Map<string, { socket: EventSocket; refs: number; cancelled: boolean }>();

/**
 * Subscribe to a mission's live event stream (shared socket, ref-counted).
 *
 * Opening a mission must not replay its history event-by-event (hundreds of re-renders),
 * so the past is fetched in one request and reduced in one store update; the socket then
 * resumes after the last seen seq. Live events are batched to one update per frame.
 */
export function useMissionStream(missionId: string | null | undefined): MissionView {
  const view = useStreams((s) => (missionId ? s.views[missionId] : undefined));
  useEffect(() => {
    if (!missionId) return;
    let entry = sockets.get(missionId);
    if (!entry) {
      const { applyMany, setStatus } = useStreams.getState();
      let queue: NexusEvent[] = [];
      let frame = 0;
      const flush = () => {
        frame = 0;
        const batch = queue;
        queue = [];
        applyMany(missionId, batch);
      };
      const socket = new EventSocket({
        missionId,
        onEvent: (e) => {
          queue.push(e);
          if (!frame) frame = requestAnimationFrame(flush);
        },
        onStatus: (st) => setStatus(missionId, st),
      });
      const created = { socket, refs: 0, cancelled: false };
      entry = created;
      sockets.set(missionId, created);
      const known = useStreams.getState().views[missionId]?.lastSeq ?? 0;
      void get<NexusEvent[]>(`/missions/${missionId}/events?after_seq=${known}&limit=10000`)
        .then((past) => !created.cancelled && applyMany(missionId, past))
        .catch(() => undefined)
        .finally(() => {
          if (!created.cancelled) socket.start(useStreams.getState().views[missionId]?.lastSeq ?? known);
        });
    }
    entry.refs += 1;
    return () => {
      const e = sockets.get(missionId);
      if (!e) return;
      e.refs -= 1;
      if (e.refs <= 0) {
        e.cancelled = true;
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
