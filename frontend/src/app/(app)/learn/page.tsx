"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { PanelSkeleton, UrlTabs } from "@/components/ui/Tabs";

const ArchitecturePanel = dynamic(
  () => import("@/components/learn/ArchitecturePanel").then((m) => m.ArchitecturePanel),
  {
    loading: PanelSkeleton,
    ssr: false,
  },
);
const CurriculumPanel = dynamic(() => import("@/components/learn/CurriculumPanel").then((m) => m.CurriculumPanel), {
  loading: PanelSkeleton,
  ssr: false,
});

const TABS = [
  { id: "architecture", label: "Architecture", render: () => <ArchitecturePanel /> },
  { id: "curriculum", label: "Curriculum Map", render: () => <CurriculumPanel /> },
];

export default function Page() {
  return (
    <>
      <PageHeader
        title="How it Works"
        description="Click through the system, and see where each Week-4 topic lives in the code."
      />
      <Suspense>
        <UrlTabs tabs={TABS} layoutId="learn-tab" />
      </Suspense>
    </>
  );
}
