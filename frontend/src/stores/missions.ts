import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface ActiveMissionState {
  /** The mission the shell's per-mission links (graph, arena, time travel) point at. */
  activeId: string | null;
  setActive: (id: string | null) => void;
}

export const useActiveMission = create<ActiveMissionState>()(
  persist((set) => ({ activeId: null, setActive: (activeId) => set({ activeId }) }), {
    name: "nexus-active-mission",
    skipHydration: true,
    storage: createJSONStorage(() => localStorage),
  }),
);
