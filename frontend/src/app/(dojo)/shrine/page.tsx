import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata = { title: "Chaos Shrine" };

export default function Page() {
  return (
    <>
      <PageHeader title="Chaos Shrine" kanji="神社" />
      <EmptyState title="Not built yet">This screen arrives in a later build phase (see docs/PLAN.md).</EmptyState>
    </>
  );
}
