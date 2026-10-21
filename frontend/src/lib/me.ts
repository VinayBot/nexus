"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "./api";

export type Role = "owner" | "operator" | "viewer";
export interface Me {
  username: string;
  role: Role;
  auth_enabled: boolean;
}

const RANK: Record<Role, number> = { viewer: 0, operator: 1, owner: 2 };

/** The signed-in account (or the local owner when auth is switched off). */
export const useMe = () =>
  useQuery({ queryKey: ["me"], queryFn: () => get<Me>("/auth/me"), staleTime: 60_000, retry: false });

/** Mirror of the backend policy, for showing or disabling controls. The server still decides. */
export function useCan(min: Role): boolean {
  const me = useMe().data;
  return Boolean(me && RANK[me.role] >= RANK[min]);
}

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  operator: "Operator",
  viewer: "Viewer",
};
