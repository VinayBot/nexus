"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useActiveMission } from "@/stores/missions";
import { useUi } from "@/stores/ui";
import { Interactions } from "./Interactions";

/** Mirrors UI preferences onto <html> data attributes that the CSS tokens key off. */
function DocumentAttributes() {
  const theme = useUi((s) => s.theme);
  const sky = useUi((s) => s.skyMood);
  const perf = useUi((s) => s.performanceMode);
  useEffect(() => {
    void useUi.persist.rehydrate();
    void useActiveMission.persist.rehydrate();
  }, []);
  useEffect(() => {
    const el = document.documentElement;
    el.dataset.theme = theme;
    el.dataset.sky = sky;
    el.dataset.perf = perf ? "on" : "off";
  }, [theme, sky, perf]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } },
      }),
  );
  const perf = useUi((s) => s.performanceMode);
  return (
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion={perf ? "always" : "user"}>
        <DocumentAttributes />
        <Interactions />
        {children}
      </MotionConfig>
    </QueryClientProvider>
  );
}
