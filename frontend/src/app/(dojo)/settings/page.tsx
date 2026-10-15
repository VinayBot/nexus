import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata = { title: "Settings" };

export default function Page() {
  return (
    <>
      <PageHeader title="Settings" kanji="設定" />
      <EmptyState title="Not built yet">This screen arrives in a later build phase (see docs/PLAN.md).</EmptyState>
    </>
  );
}
