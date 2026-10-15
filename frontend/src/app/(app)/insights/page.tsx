"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { PanelSkeleton, UrlTabs } from "@/components/ui/Tabs";

// each tab's code (charts etc.) loads only when the tab is opened
const ObservatoryPanel = dynamic(
  () => import("@/components/insights/ObservatoryPanel").then((m) => m.ObservatoryPanel),
  {
    loading: PanelSkeleton,
    ssr: false,
  },
);
const BenchmarksPanel = dynamic(() => import("@/components/insights/BenchmarksPanel").then((m) => m.BenchmarksPanel), {
  loading: PanelSkeleton,
  ssr: false,
});
const UnderTheHoodPanel = dynamic(
  () => import("@/components/insights/UnderTheHoodPanel").then((m) => m.UnderTheHoodPanel),
  { loading: PanelSkeleton, ssr: false },
);

const TABS = [
  { id: "observatory", label: "Observatory", render: () => <ObservatoryPanel /> },
  { id: "benchmarks", label: "Benchmarks", render: () => <BenchmarksPanel /> },
  { id: "lab", label: "Under the Hood", render: () => <UnderTheHoodPanel /> },
];

export default function Page() {
  return (
    <>
      <PageHeader
        title="Insights"
        description="Traces, tokens, latency and live benchmarks — measured on this machine."
      />
      <Suspense>
        <UrlTabs tabs={TABS} layoutId="insights-tab" />
      </Suspense>
    </>
  );
}
