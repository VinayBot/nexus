"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "./api";

export interface Mission {
  id: string;
  title: string;
  task: string;
  playbook: string | null;
  status: "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";
  outcome: string | null;
  source: string;
  tokens: number;
  error: string | null;
  report: Record<string, unknown> | null;
  inputs: Record<string, unknown>;
  forked_from: string | null;
  created_at: number;
  updated_at: number;
}

export interface PlaybookInfo {
  id: string;
  title: string;
  description: string;
  tournament_mode: "answer" | "code" | null;
  approve_team: boolean;
}

export interface Approval {
  id: string;
  mission_id: string;
  kind: "approve_action" | "approve_team" | "answer_question" | "edit_plan";
  status: string;
  payload: Record<string, unknown> & { summary?: string };
  decision: Record<string, unknown> | null;
  risk_level: string | null;
  email_status: string | null;
  created_at: number;
  decided_at: number | null;
}

export interface Ticket {
  id: string;
  title: string;
  body: string;
  status: string;
  labels: string[];
  comments: { author: string; body: string; ts: number }[];
  attachments: { name: string; size: number; ts?: number }[];
}

export const useMissions = (limit = 30) =>
  useQuery({
    queryKey: ["missions", limit],
    queryFn: () => get<Mission[]>(`/missions?limit=${limit}`),
    refetchInterval: 15_000,
  });

/**
 * One mission. Live events refresh it, but a mission can finish before the event
 * socket is ready (fast missions, reconnects): until it is finished, poll as a backstop
 * so the page never stays on "running" without showing the result.
 */
export const useMission = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["missions", "one", id],
    queryFn: () => get<Mission>(`/missions/${id}`),
    enabled: Boolean(id),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === "completed" || status === "failed" || status === "cancelled" ? false : 3_000;
    },
  });

export const usePlaybooks = () =>
  useQuery({ queryKey: ["playbooks"], queryFn: () => get<PlaybookInfo[]>("/playbooks"), staleTime: 60_000 });

export const useApprovals = (status: string | null = "pending") =>
  useQuery({
    queryKey: ["approvals", status],
    queryFn: () => get<Approval[]>(`/approvals${status ? `?status=${status}` : "?status="}`),
    refetchInterval: 20_000,
  });

export const useTickets = () => useQuery({ queryKey: ["tickets"], queryFn: () => get<Ticket[]>("/tickets") });
