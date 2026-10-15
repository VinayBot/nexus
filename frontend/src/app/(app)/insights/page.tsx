"use client";

import { Suspense } from "react";
import { BenchmarksPanel } from "@/components/insights/BenchmarksPanel";
import { ObservatoryPanel } from "@/components/insights/ObservatoryPanel";
import { UnderTheHoodPanel } from "@/components/insights/UnderTheHoodPanel";
import { PageHeader } from "@/components/ui/PageHeader";
import { UrlTabs } from "@/components/ui/Tabs";

const TABS = [
  { id: "observatory", label: "Observatory", render: () => <ObservatoryPanel /> },
  { id: "benchmarks", label: "Benchmarks", render: () => <BenchmarksPanel /> },
  { id: "lab", label: "Under the Hood", render: () => <UnderTheHoodPanel /> },
];

export default function Page() {
  return (
    <>
      <PageHeader title="Insights" description="Traces, tokens, latency and live benchmarks — measured on this machine." />
      <Suspense>
        <UrlTabs tabs={TABS} layoutId="insights-tab" />
      </Suspense>
    </>
  );
}
