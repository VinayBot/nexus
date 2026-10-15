import { MissionPicker } from "@/components/ui/MissionPicker";

export const metadata = { title: "Scroll of Time" };

export default function Page() {
  return (
    <MissionPicker
      title="Scroll of Time"
      kanji="時"
      target="/timetravel"
      hint="Pick a mission to travel through its checkpoints."
    />
  );
}
