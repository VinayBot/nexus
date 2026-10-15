"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "./api";
import type { Avatar } from "@/components/robots/Robot";

export interface AgentInfo {
  id: string;
  name: string;
  title: string;
  role: string;
  persona: string;
  system_prompt: string;
  model_role: "main" | "fast";
  temperature: number;
  tools: string[];
  max_steps: number;
  num_ctx: number;
  strategy: string | null;
  avatar: Avatar;
  risk_level: string;
  builtin: boolean;
  stats: Record<string, unknown> | null;
}

/** Fallback looks so robots render before the registry loads (or for unknown ids). */
export const FALLBACK_AVATARS: Record<string, Avatar> = {
  shogun: { color: "#F7A440", headband: "#F7A440", prop: "war_fan", size: "large" },
  sensei: { color: "#E9D8A6", headband: "#7B5CFF", prop: "scroll" },
  kagemi: { color: "#5B6CFF", headband: "#2E2A5A", prop: "lens" },
  kanji: { color: "#141414", headband: "#3B3B3B", prop: "brush" },
  tetsu: { color: "#F2662A", headband: "#F2662A", prop: "hammer" },
  mamoru: { color: "#3FD18B", headband: "#3FD18B", prop: "shield" },
  ronin_a: { color: "#C8341F", headband: "#C8341F", prop: "katana" },
  ronin_b: { color: "#4FE3F0", headband: "#4FE3F0", prop: "katana" },
  ronin_c: { color: "#FFB020", headband: "#FFB020", prop: "katana" },
  hakari: { color: "#D9C38A", headband: "#8E1B17", prop: "scale" },
  kiri: { color: "#B0B7C3", headband: "#5A5F6B", prop: "arms_folded" },
  hikyaku: { color: "#FF8FA3", headband: "#C8341F", prop: "envelope" },
  kuro: { color: "#2B2B2B", headband: "#FFB020", prop: "lantern" },
  hikari: { color: "#4FE3F0", headband: "#4FE3F0", prop: "glow", size: "small" },
};

export const AGENT_NAMES: Record<string, string> = {
  shogun: "Shogun",
  sensei: "Sensei",
  kagemi: "Kagemi",
  kanji: "Kanji",
  tetsu: "Tetsu",
  mamoru: "Mamoru",
  ronin_a: "Ronin A",
  ronin_b: "Ronin B",
  ronin_c: "Ronin C",
  hakari: "Hakari",
  kiri: "Kiri",
  hikyaku: "Hikyaku",
  kuro: "Kuro",
  hikari: "Hikari",
};

export function useAgents() {
  return useQuery({ queryKey: ["agents"], queryFn: () => get<AgentInfo[]>("/agents"), staleTime: 30_000 });
}

export function avatarOf(id: string, agents?: AgentInfo[]): Avatar {
  return (
    agents?.find((a) => a.id === id)?.avatar ??
    FALLBACK_AVATARS[id] ?? { color: "#4FE3F0", headband: "#C8341F", prop: "none" }
  );
}

export function nameOf(id: string, agents?: AgentInfo[]): string {
  return agents?.find((a) => a.id === id)?.name ?? AGENT_NAMES[id] ?? id;
}
