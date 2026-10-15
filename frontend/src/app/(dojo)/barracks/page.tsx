import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata = { title: "Barracks" };

export default function Page() {
  return (
    <>
      <PageHeader title="Barracks" kanji="兵舎" />
      <EmptyState title="Not built yet">This screen arrives in a later build phase (see docs/PLAN.md).</EmptyState>
    </>
  );
}
