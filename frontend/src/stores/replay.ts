"use client";

import { useEffect, useRef, useState } from "react";
import { get } from "@/lib/api";
import type { NexusEvent } from "@/lib/events";
import { emptyView, reduceMission, type MissionView } from "@/lib/missionView";

export const SPEEDS = [0.5, 1, 2, 4, 8] as const;
const MAX_GAP_MS = 2500; // long real pauses (e.g. waiting for a human) are compressed

/**
 * Replay a finished mission from its persisted events, through the same reducer
 * Live mode uses — so the Dojo looks exactly as it did, at any speed.
 */
export function useReplay(missionId: string | null, enabled: boolean, speed: number) {
  const [view, setView] = useState<MissionView>(emptyView(missionId));
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [playing, setPlaying] = useState(true);
  const [run, setRun] = useState(0);
  const events = useRef<NexusEvent[]>([]);
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const playingRef = useRef(playing);
  playingRef.current = playing;

  useEffect(() => {
    if (!enabled || !missionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      events.current = await get<NexusEvent[]>(`/missions/${missionId}/events?limit=10000`);
      if (cancelled) return;
      let v = emptyView(missionId);
      setView(v);
      setProgress({ done: 0, total: events.current.length });
      let i = 0;
      const step = () => {
        if (cancelled) return;
        if (!playingRef.current) {
          timer = setTimeout(step, 200);
          return;
        }
        const e = events.current[i];
        if (!e) return;
        // shift timestamps to "now" so time-based robot decay behaves as it did live
        v = reduceMission(v, { ...e, ts: Date.now() / 1000 } as NexusEvent);
        i += 1;
        setView(v);
        setProgress({ done: i, total: events.current.length });
        const nextEv = events.current[i];
        if (!nextEv) return;
        const gap = Math.min(MAX_GAP_MS, Math.max(0, (nextEv.ts - e.ts) * 1000));
        timer = setTimeout(step, gap / speedRef.current);
      };
      step();
    })().catch(() => setProgress({ done: 0, total: 0 }));
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [enabled, missionId, run]);

  return { view, progress, playing, setPlaying, restart: () => setRun((r) => r + 1) };
}
