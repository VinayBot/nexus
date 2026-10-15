import { MissionPicker } from "@/components/ui/MissionPicker";

export const metadata = { title: "Council Arena" };

export default function Page() {
  return (
    <MissionPicker
      title="Council Arena"
      kanji="闘技"
      target="/arena"
      hint="Pick a mission to replay its council and tournaments."
    />
  );
}
