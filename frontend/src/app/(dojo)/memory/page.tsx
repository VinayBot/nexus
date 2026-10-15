import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata = { title: "Memory Palace" };

export default function Page() {
  return (
    <>
      <PageHeader title="Memory Palace" kanji="記憶" />
      <EmptyState title="Not built yet">This screen arrives in a later build phase (see docs/PLAN.md).</EmptyState>
    </>
  );
}
