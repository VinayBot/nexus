import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type Theme = "sunset" | "night";
export type Accent = "violet" | "emerald" | "teal" | "rose" | "ember";
/** The sky reflects system state: calm, an active incident, or a successful heal. */
export type SkyMood = "idle" | "incident" | "dawn";

interface UiState {
  theme: Theme;
  accent: Accent;
  navCollapsed: boolean;
  soundOn: boolean;
  performanceMode: boolean;
  skyMood: SkyMood;
  setTheme: (t: Theme) => void;
  setAccent: (a: Accent) => void;
  toggleTheme: () => void;
  toggleNav: () => void;
  toggleSound: () => void;
  togglePerformance: () => void;
  setSkyMood: (m: SkyMood) => void;
}

/** Client-only UI preferences. Persisted per browser; nothing here is mission state. */
export const useUi = create<UiState>()(
  persist(
    (set) => ({
      theme: "sunset",
      accent: "violet",
      navCollapsed: false,
      soundOn: false,
      performanceMode: false,
      skyMood: "idle",
      setTheme: (theme) => set({ theme }),
      setAccent: (accent) => set({ accent }),
      toggleTheme: () => set((s) => ({ theme: s.theme === "sunset" ? "night" : "sunset" })),
      toggleNav: () => set((s) => ({ navCollapsed: !s.navCollapsed })),
      toggleSound: () => set((s) => ({ soundOn: !s.soundOn })),
      togglePerformance: () => set((s) => ({ performanceMode: !s.performanceMode })),
      setSkyMood: (skyMood) => set({ skyMood }),
    }),
    {
      name: "nexus-ui",
      // v2: the default accent moved from Ember (orange) to Violet; move saved browsers too
      version: 2,
      migrate: (saved, version) => {
        const state = (saved ?? {}) as Partial<UiState>;
        return (version < 2 ? { ...state, accent: "violet" } : state) as UiState;
      },
      skipHydration: true, // rehydrated after mount so SSR and first client render match
      storage: createJSONStorage(() => localStorage),
      partialize: ({ theme, accent, navCollapsed, soundOn, performanceMode }) => ({
        theme,
        accent,
        navCollapsed,
        soundOn,
        performanceMode,
      }),
    },
  ),
);
