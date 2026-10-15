"use client";

import { Suspense } from "react";
import { ArchitecturePanel } from "@/components/learn/ArchitecturePanel";
import { CurriculumPanel } from "@/components/learn/CurriculumPanel";
import { PageHeader } from "@/components/ui/PageHeader";
import { UrlTabs } from "@/components/ui/Tabs";

const TABS = [
  { id: "architecture", label: "Architecture", render: () => <ArchitecturePanel /> },
  { id: "curriculum", label: "Curriculum Map", render: () => <CurriculumPanel /> },
];

export default function Page() {
  return (
    <>
      <PageHeader title="How it Works" description="Click through the system, and see where each Week-4 topic lives in the code." />
      <Suspense>
        <UrlTabs tabs={TABS} layoutId="learn-tab" />
      </Suspense>
    </>
  );
}
