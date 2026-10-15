import { create } from "zustand";

interface MissionsState {
  /** The mission the shell's per-mission links (graph, arena, time travel) point at. */
  activeId: string | null;
  setActive: (id: string | null) => void;
}

export const useMissions = create<MissionsState>()((set) => ({
  activeId: null,
  setActive: (activeId) => set({ activeId }),
}));
