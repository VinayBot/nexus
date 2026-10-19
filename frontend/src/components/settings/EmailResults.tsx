"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Mail, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { del, get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";

interface NotifyStatus {
  to: string | null;
  enabled: boolean;
  delivery: "smtp" | "mailpit";
  smtp: string;
  account: string | null;
  provider: string | null;
}

/** Settings → Email results: where each mission's result is emailed, and how. */
export function EmailResults() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["notify"], queryFn: () => get<NotifyStatus>("/notify") });
  const s = status.data;
  const [to, setTo] = useState("");
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => {
    if (s) {
      setTo(s.to ?? "");
      setAccount((a) => a || s.account || s.to || "");
    }
  }, [s]);
  const onSaved = (d: NotifyStatus) => qc.setQueryData(["notify"], d);
  const save = useMutation({
    mutationFn: (body: { to: string; enabled: boolean }) => put<NotifyStatus>("/notify", body),
    onSuccess: onSaved,
  });
  const connect = useMutation({
    mutationFn: () =>
      put<NotifyStatus>("/notify/smtp", { provider: "gmail", username: account, app_password: password }),
    onSuccess: (d) => {
      setPassword("");
      onSaved(d);
    },
  });
  const disconnect = useMutation({ mutationFn: () => del<NotifyStatus>("/notify/smtp"), onSuccess: onSaved });
  const test = useMutation({ mutationFn: () => post<{ status: string }>("/notify/test") });
  const error = save.error ?? connect.error ?? disconnect.error ?? test.error;

  return (
    <section className="panel p-4 xl:col-span-2" aria-label="Email results">
      <div className="flex flex-wrap items-center gap-2">
        <Mail className="size-4 text-accent" />
        <h2 className="panel-title text-sm">Email results</h2>
        <span className="text-xs text-faint">
          Every finished or failed mission is emailed to you, with its full result.
        </span>
      </div>
      {s && (
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <label className="block text-xs text-muted">
              Send results to
              <div className="mt-1 flex gap-2">
                <input
                  type="email"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  className="min-w-0 flex-1 rounded-lg border border-border bg-black/25 px-3 py-2 text-sm text-text"
                  aria-label="Result email address"
                />
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={save.isPending || to === (s.to ?? "")}
                  onClick={() => save.mutate({ to, enabled: s.enabled })}
                >
                  Save
                </button>
              </div>
            </label>
            <label className="flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={(e) => save.mutate({ to: s.to ?? to, enabled: e.target.checked })}
                aria-label="Email mission results"
              />
              Email mission results
            </label>
            <p
              className={cn(
                "rounded-lg px-3 py-2 text-xs",
                s.delivery === "smtp" ? "bg-success/10 text-success" : "bg-warning/10 text-warning",
              )}
            >
              {s.delivery === "smtp" ? (
                <>
                  <CheckCircle2 className="mr-1 inline size-3.5" /> Delivering through {s.account} ({s.smtp}).
                </>
              ) : (
                <>
                  Not connected to a real mail server yet: emails go to the local test inbox (Mailpit, {s.smtp}).
                  Connect Gmail on the right to receive them in your inbox.
                </>
              )}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={!s.to || test.isPending}
                onClick={() => test.mutate()}
              >
                <Send className="size-3.5" /> {test.isPending ? "Sending…" : "Send test email"}
              </button>
              {test.data && (
                <span className={cn("text-xs", test.data.status === "sent" ? "text-success" : "text-warning")}>
                  {test.data.status === "sent"
                    ? `Sent. Check ${s.to}.`
                    : "Could not reach the mail server; kept in the outbox."}
                </span>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border p-3.5">
            <p className="text-sm font-semibold text-text">Connect Gmail</p>
            {s.delivery === "smtp" && s.provider ? (
              <div className="mt-2 flex items-center gap-2 text-xs text-muted">
                Connected as <span className="text-text">{s.account}</span>
                <button type="button" className="btn btn-ghost btn-sm ml-auto" onClick={() => disconnect.mutate()}>
                  Disconnect
                </button>
              </div>
            ) : (
              <>
                <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-xs text-muted">
                  <li>Turn on 2-Step Verification for your Google account.</li>
                  <li>
                    Create an App Password:{" "}
                    <a
                      href="https://myaccount.google.com/apppasswords"
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent hover:underline"
                    >
                      myaccount.google.com/apppasswords <ExternalLink className="inline size-3" />
                    </a>
                  </li>
                  <li>Paste the 16-letter password below. It is stored only on this Mac.</li>
                </ol>
                <div className="mt-2 grid gap-2">
                  <input
                    type="email"
                    value={account}
                    onChange={(e) => setAccount(e.target.value)}
                    className="rounded-lg border border-border bg-black/25 px-3 py-2 text-sm text-text"
                    aria-label="Gmail address"
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="off"
                    className="rounded-lg border border-border bg-black/25 px-3 py-2 font-mono text-sm text-text"
                    aria-label="Gmail app password"
                  />
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={!account || password.replace(/\s/g, "").length < 8 || connect.isPending}
                    onClick={() => connect.mutate()}
                  >
                    Connect
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error.message}</p>}
    </section>
  );
}
