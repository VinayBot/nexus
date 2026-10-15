import { MissionPicker } from "@/components/ui/MissionPicker";

export const metadata = { title: "Live Graph" };

export default function Page() {
  return (
    <MissionPicker title="Live Graph" kanji="流れ" target="/graph" hint="Pick a mission to watch its LangGraph run." />
  );
}
