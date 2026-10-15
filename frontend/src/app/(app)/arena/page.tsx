import { MissionPicker } from "@/components/ui/MissionPicker";

export const metadata = { title: "Arena" };

export default function Page() {
  return <MissionPicker title="Arena" target="/arena" hint="Pick a mission to replay its council and tournaments." />;
}
