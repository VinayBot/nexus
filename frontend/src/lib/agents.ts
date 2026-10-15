"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "./api";
import type { Avatar } from "@/components/robots/Robot";
import { canonicalId } from "./agentIds";

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
  commander: { color: "#2A2F3A", accent: "#F7A440", prop: "staff", size: "large" },
  sage: { color: "#E8ECF2", accent: "#9D7BFF", prop: "tablet" },
  echo: { color: "#E8ECF2", accent: "#5B8CFF", prop: "scanner" },
  quill: { color: "#C7CBD6", accent: "#FFD08A", prop: "stylus" },
  forge: { color: "#E8ECF2", accent: "#F2662A", prop: "wrench" },
  aegis: { color: "#E8ECF2", accent: "#3FD18B", prop: "shield" },
  blaze: { color: "#2A2F3A", accent: "#FF4D4F", prop: "blade" },
  volt: { color: "#2A2F3A", accent: "#FFD23F", prop: "blade" },
  frost: { color: "#E8ECF2", accent: "#4FE3F0", prop: "blade" },
  arbiter: { color: "#E8ECF2", accent: "#E9C46A", prop: "scale" },
  vex: { color: "#2A2F3A", accent: "#FF4FB6", prop: "none" },
  swift: { color: "#E8ECF2", accent: "#FF8FA3", prop: "jets" },
  hawk: { color: "#2A2F3A", accent: "#FFB020", prop: "beacon" },
  nova: { color: "#E8ECF2", accent: "#4FE3F0", prop: "halo", size: "small" },
};

export const AGENT_NAMES: Record<string, string> = {
  commander: "Commander",
  sage: "Sage",
  echo: "Echo",
  quill: "Quill",
  forge: "Forge",
  aegis: "Aegis",
  blaze: "Blaze",
  volt: "Volt",
  frost: "Frost",
  arbiter: "Arbiter",
  vex: "Vex",
  swift: "Swift",
  hawk: "Hawk",
  nova: "Nova",
};

export function useAgents() {
  return useQuery({ queryKey: ["agents"], queryFn: () => get<AgentInfo[]>("/agents"), staleTime: 30_000 });
}

export function avatarOf(rawId: string, agents?: AgentInfo[]): Avatar {
  const id = canonicalId(rawId);
  return (
    agents?.find((a) => a.id === id)?.avatar ??
    FALLBACK_AVATARS[id] ?? { color: "#E8ECF2", accent: "#4FE3F0", prop: "none" }
  );
}

export function nameOf(rawId: string, agents?: AgentInfo[]): string {
  const id = canonicalId(rawId);
  return agents?.find((a) => a.id === id)?.name ?? AGENT_NAMES[id] ?? id;
}
