import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata = { title: "Scroll of Time" };

export default function Page() {
  return (
    <>
      <PageHeader title="Scroll of Time" kanji="時" />
      <EmptyState title="Not built yet">This screen arrives in a later build phase (see docs/PLAN.md).</EmptyState>
    </>
  );
}
