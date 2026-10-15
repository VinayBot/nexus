"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { EventSocket } from "@/lib/ws";
import { useLive } from "@/stores/live";
import { useUi } from "@/stores/ui";

/**
 * Opens the global event channel once for the whole app. Real events drive the
 * shared stores, the dynamic sky (incident → crimson, successful heal → dawn) and
 * cache invalidation, so every screen stays live without polling.
 */
export function LiveBridge() {
  const qc = useQueryClient();
  useEffect(() => {
    let dawnTimer: ReturnType<typeof setTimeout> | null = null;
    const socket = new EventSocket({
      missionId: null,
      onStatus: (s) => useLive.getState().setSocket(s),
      onEvent: (e) => {
        useLive.getState().ingest(e);
        const ui = useUi.getState();
        switch (e.type) {
          case "incident.detected":
            ui.setSkyMood("incident");
            break;
          case "service.health":
            if (e.payload.status !== "healthy" && ui.skyMood === "idle") ui.setSkyMood("incident");
            if (e.payload.status === "healthy" && ui.skyMood === "incident") ui.setSkyMood("idle");
            break;
          case "mission.completed":
            if (e.payload.outcome === "success" && ui.skyMood === "incident") {
              ui.setSkyMood("dawn");
              if (dawnTimer) clearTimeout(dawnTimer);
              dawnTimer = setTimeout(() => useUi.getState().setSkyMood("idle"), 45_000);
            }
            break;
        }
        if (e.type.startsWith("mission.") || e.type === "interrupt.resolved") {
          void qc.invalidateQueries({ queryKey: ["missions"] });
        }
        // resolved approvals are refreshed by the card itself after its seal/tear animation
        if (e.type === "interrupt.raised") void qc.invalidateQueries({ queryKey: ["approvals"] });
        if (e.type === "incident.detected" || e.type === "chaos.toggled") {
          void qc.invalidateQueries({ queryKey: ["chaos"] });
          void qc.invalidateQueries({ queryKey: ["incidents"] });
        }
      },
    });
    socket.start();
    return () => {
      socket.stop();
      if (dawnTimer) clearTimeout(dawnTimer);
    };
  }, [qc]);
  return null;
}
