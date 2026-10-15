import { MissionPicker } from "@/components/ui/MissionPicker";

export const metadata = { title: "Time Travel" };

export default function Page() {
  return (
    <MissionPicker
      title="Time Travel"
      target="/timetravel"
      hint="Pick a mission to travel through its checkpoints."
    />
  );
}
