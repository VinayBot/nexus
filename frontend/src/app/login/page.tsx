"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { LogoMark, Wordmark } from "@/components/brand/Logo";
import { StudioBackdrop } from "@/components/layout/StudioBackdrop";
import { get, post } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";

interface Session {
  token: string;
  username: string;
  role: string;
}

const field =
  "w-full rounded-lg border border-border bg-black/30 px-3 py-2.5 text-sm text-text focus-visible:border-[var(--accent-strong)]";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const next = params.get("next") || "/missions";
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: () => get<{ auth_enabled: boolean; setup_required: boolean }>("/auth/status"),
    retry: 1,
  });
  const setup = Boolean(status.data?.setup_required);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  useEffect(() => {
    if (status.data && !status.data.auth_enabled) router.replace(next); // auth is off
    if (status.data && getToken() && !setup) router.replace(next); // already signed in
  }, [status.data, setup, next, router]);

  const submit = useMutation({
    mutationFn: () => post<Session>(setup ? "/auth/setup" : "/auth/login", { username, password }),
    onSuccess: (s) => {
      setToken(s.token);
      qc.clear();
      router.replace(next);
    },
  });
  const mismatch = setup && confirm.length > 0 && confirm !== password;
  const canSubmit = username.length >= 3 && password.length >= 8 && (!setup || confirm === password);

  return (
    <main className="grid min-h-dvh place-items-center p-4">
      <StudioBackdrop />
      <motion.form
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 26 }}
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) submit.mutate();
        }}
        className="panel breathe w-full max-w-sm space-y-4 p-6"
        aria-label={setup ? "Create the owner account" : "Sign in"}
      >
        <div className="flex items-center gap-3">
          <LogoMark size={36} />
          <Wordmark className="text-xl" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-text">{setup ? "Create the owner account" : "Sign in"}</h1>
          <p className="mt-1 text-sm text-muted">
            {setup
              ? "First run: this account can do everything, including adding operators and viewers."
              : "Use the account your NEXUS owner gave you."}
          </p>
        </div>
        {status.isLoading ? (
          <Loader2 className="mx-auto size-5 animate-spin text-accent" />
        ) : (
          <>
            <label className="block space-y-1 text-xs text-muted">
              Username
              <input
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value.trim())}
                className={field}
                aria-label="Username"
              />
            </label>
            <label className="block space-y-1 text-xs text-muted">
              Password {setup && "(8 characters or more)"}
              <input
                type="password"
                autoComplete={setup ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={field}
                aria-label="Password"
              />
            </label>
            {setup && (
              <label className="block space-y-1 text-xs text-muted">
                Repeat the password
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className={field}
                  aria-label="Repeat the password"
                />
              </label>
            )}
            {mismatch && <p className="text-xs text-danger">The passwords do not match.</p>}
            {submit.isError && (
              <p className="rounded-md bg-danger/10 px-3 py-2 text-xs text-danger" role="alert">
                {submit.error.message}
              </p>
            )}
            <button type="submit" disabled={!canSubmit || submit.isPending} className="btn btn-primary w-full">
              {setup ? <ShieldCheck className="size-4" /> : <LogIn className="size-4" />}
              {submit.isPending ? "Please wait…" : setup ? "Create account and sign in" : "Sign in"}
            </button>
          </>
        )}
        {status.isError && (
          <p className="text-xs text-danger">The NEXUS backend is not reachable. Start it with `make dev`.</p>
        )}
      </motion.form>
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
