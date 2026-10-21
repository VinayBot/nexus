"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Trash2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { del, get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";
import { ROLE_LABEL, useCan, useMe, type Role } from "@/lib/me";

interface UserRow {
  username: string;
  role: Role;
  created_at: number;
}

const ROLES: { id: Role; can: string }[] = [
  { id: "owner", can: "everything, including settings, models, users and deleting" },
  { id: "operator", can: "start and cancel missions, approve or reject, time travel" },
  { id: "viewer", can: "read everything, change nothing" },
];

const field = "rounded-lg border border-border bg-black/25 px-3 py-2 text-sm text-text";

/** Settings → Users (owner only): who can sign in, and with which role. */
export function UsersPanel() {
  const qc = useQueryClient();
  const me = useMe().data;
  const isOwner = useCan("owner");
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => get<UserRow[]>("/auth/users"),
    enabled: isOwner && Boolean(me?.auth_enabled),
  });
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const refresh = () => void qc.invalidateQueries({ queryKey: ["users"] });
  const add = useMutation({
    mutationFn: () => post("/auth/users", { username: name, password, role }),
    onSuccess: () => {
      setName("");
      setPassword("");
      refresh();
    },
  });
  const change = useMutation({
    mutationFn: (u: { username: string; role: Role }) => put(`/auth/users/${u.username}`, { role: u.role }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (u: string) => del(`/auth/users/${u}`), onSuccess: refresh });
  if (!isOwner || !me?.auth_enabled) return null;
  const error = add.error ?? change.error ?? remove.error;

  return (
    <section className="panel p-4 xl:col-span-2" aria-label="Users" data-tour="users">
      <div className="flex flex-wrap items-center gap-2">
        <Users className="size-4 text-accent" />
        <h2 className="panel-title text-sm">Users and roles</h2>
        <span className="text-xs text-faint">
          Each person signs in with their own account. Decisions are logged by name.
        </span>
      </div>
      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ul className="space-y-1.5">
          <AnimatePresence initial={false}>
            {users.data?.map((u) => (
              <motion.li
                key={u.username}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="flex items-center gap-2 rounded-lg border border-border px-3 py-2"
              >
                <span className="grid size-7 place-items-center rounded-full bg-[rgb(var(--accent-rgb)/0.2)] text-xs font-bold text-text uppercase">
                  {u.username.slice(0, 1)}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-text">
                  {u.username}
                  {u.username === me.username && <span className="text-faint"> (you)</span>}
                </span>
                <select
                  value={u.role}
                  onChange={(e) => change.mutate({ username: u.username, role: e.target.value as Role })}
                  className="rounded-md border border-border bg-black/30 px-2 py-1 text-xs"
                  aria-label={`Role of ${u.username}`}
                >
                  {ROLES.map((r) => (
                    <option key={r.id} value={r.id}>
                      {ROLE_LABEL[r.id]}
                    </option>
                  ))}
                </select>
                {u.username !== me.username && (
                  <button
                    type="button"
                    onClick={() => remove.mutate(u.username)}
                    aria-label={`Remove ${u.username}`}
                    className="grid size-7 place-items-center rounded-md text-faint hover:bg-danger/15 hover:text-danger"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        <form
          className="space-y-2 rounded-xl border border-border p-3"
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate();
          }}
        >
          <p className="text-sm font-semibold text-text">Add a user</p>
          <span className="block text-[11px] text-faint">Username</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value.trim())}
            className={cn(field, "w-full")}
            aria-label="New username"
          />
          <span className="block text-[11px] text-faint">Password (8 characters or more)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            className={cn(field, "w-full")}
            aria-label="New user password"
          />
          <div className="space-y-1" role="radiogroup" aria-label="Role">
            {ROLES.map((r) => (
              <label key={r.id} className="flex items-start gap-2 text-xs text-muted">
                <input
                  type="radio"
                  name="role"
                  checked={role === r.id}
                  onChange={() => setRole(r.id)}
                  className="mt-0.5"
                />
                <span>
                  <b className="text-text">{ROLE_LABEL[r.id]}</b>: {r.can}
                </span>
              </label>
            ))}
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={name.length < 3 || password.length < 8 || add.isPending}
          >
            <UserPlus className="size-3.5" /> Add user
          </button>
        </form>
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error.message}</p>}
    </section>
  );
}
