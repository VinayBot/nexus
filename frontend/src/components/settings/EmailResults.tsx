"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, ExternalLink, Mail, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { del, get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";

interface NotifyStatus {
  to: string | null;
  enabled: boolean;
  delivery: "google" | "smtp" | "mailpit";
  smtp: string;
  last_error: string | null;
  google_account: string | null;
  google_ready: boolean;
  waiting: number;
}

/** What each `google_error` code from the sign-in redirect means. */
const GOOGLE_ERRORS: Record<string, string> = {
  cancelled: "you cancelled it, or Google returned no sign-in.",
  expired: "the sign-in link expired. Start again.",
  not_configured: "the Google client ID and secret are not set yet.",
  refused: "Google refused it. Check the client ID, secret and redirect URI.",
  failed: "something went wrong. Check the server log and try again.",
};

/** Google's "G" mark, in Google's colours as their sign-in guidelines ask. */
function GoogleG() {
  return (
    <svg viewBox="0 0 48 48" className="size-4" aria-hidden>
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

const field = "rounded-lg border border-border bg-black/25 px-3 py-2 text-sm text-text";
const link = "text-accent hover:underline";

function SetupSteps({ onSaved }: { onSaved: (d: NotifyStatus) => void }) {
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const save = useMutation({
    mutationFn: () => put<NotifyStatus>("/notify/google/client", { client_id: clientId, client_secret: clientSecret }),
    onSuccess: (d) => {
      setClientSecret("");
      onSaved(d);
    },
  });
  const ext = <ExternalLink className="inline size-3" />;
  return (
    <div className="mt-1 space-y-2">
      <p className="text-xs text-muted">
        Google asks every app that sends Gmail to be registered once (free, about 5 minutes). After that you only click{" "}
        <b>Sign in with Google</b>.
      </p>
      <ol className="list-decimal space-y-1 pl-4 text-xs text-muted">
        <li>
          <a href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noreferrer" className={link}>
            Create a Google Cloud project {ext}
          </a>{" "}
          named NEXUS.
        </li>
        <li>
          Enable the{" "}
          <a
            href="https://console.cloud.google.com/apis/library/gmail.googleapis.com"
            target="_blank"
            rel="noreferrer"
            className={link}
          >
            Gmail API {ext}
          </a>
          .
        </li>
        <li>
          Open{" "}
          <a href="https://console.cloud.google.com/auth/overview" target="_blank" rel="noreferrer" className={link}>
            Google Auth Platform {ext}
          </a>{" "}
          → Get started: app name NEXUS, your email, audience <b>External</b>. Then Audience → add your email as a test
          user.
        </li>
        <li>
          Clients → <b>Create client</b> → type <b>Desktop app</b> → Create, and copy the ID and secret.
        </li>
      </ol>
      <div className="grid gap-2">
        <span className="text-[11px] text-faint">Client ID</span>
        <input
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className={field}
          aria-label="Google client ID"
          spellCheck={false}
        />
        <span className="text-[11px] text-faint">Client secret</span>
        <input
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          autoComplete="off"
          className={cn(field, "font-mono")}
          aria-label="Google client secret"
        />
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={!clientId || !clientSecret || save.isPending}
          onClick={() => save.mutate()}
        >
          Save and continue
        </button>
        {save.isError && <p className="text-xs text-danger">{save.error.message}</p>}
      </div>
    </div>
  );
}

/** Settings → Email results: who sends (your Google account) and the rule for when. */
export function EmailResults() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["notify"], queryFn: () => get<NotifyStatus>("/notify") });
  const s = status.data;
  const [to, setTo] = useState("");
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    if (s) setTo(s.to ?? "");
  }, [s]);
  useEffect(() => {
    // Google sends the browser back to /settings?google=connected or ?google_error=<code>
    const q = new URLSearchParams(window.location.search);
    const ok = q.get("google");
    const bad = q.get("google_error");
    if (ok) setBanner({ ok: true, text: "Signed in with Google. Results will be sent from this account." });
    if (bad)
      setBanner({ ok: false, text: `Google sign-in did not finish: ${GOOGLE_ERRORS[bad] ?? GOOGLE_ERRORS.failed}` });
    if (ok || bad) window.history.replaceState(null, "", "/settings");
  }, []);
  const onSaved = (d: NotifyStatus) => qc.setQueryData(["notify"], d);
  const save = useMutation({
    mutationFn: (body: { to: string; enabled: boolean }) => put<NotifyStatus>("/notify", body),
    onSuccess: onSaved,
  });
  const signIn = useMutation({
    mutationFn: () => get<{ url: string }>("/notify/google/start"),
    onSuccess: ({ url }) => window.location.assign(url),
  });
  const signOut = useMutation({ mutationFn: () => del<NotifyStatus>("/notify/google"), onSuccess: onSaved });
  const resend = useMutation({
    mutationFn: () => post<{ sent: number; failed: number }>("/notify/resend"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["notify"] }),
  });
  const test = useMutation({ mutationFn: () => post<{ status: string; error: string | null }>("/notify/test") });
  const error = save.error ?? signIn.error ?? signOut.error ?? test.error;

  return (
    <section className="panel p-4 xl:col-span-2" aria-label="Email results" data-tour="email-results">
      <div className="flex flex-wrap items-center gap-2">
        <Mail className="size-4 text-accent" />
        <h2 className="panel-title text-sm">Email results</h2>
      </div>
      <p className="mt-1 text-sm text-muted">
        Results are emailed <b className="text-text">only when you ask in the prompt</b>, for example{" "}
        <i>“…and send the output to name@example.com”</i> or <i>“…email me the answer”</i>. They always show in the app
        too.
      </p>
      <AnimatePresence>
        {banner && (
          <motion.p
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={cn(
              "mt-3 rounded-lg px-3 py-2 text-sm",
              banner.ok ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
            )}
            role="status"
          >
            {banner.text}
          </motion.p>
        )}
      </AnimatePresence>
      {s && (
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-border p-4">
            <p className="text-sm font-semibold text-text">1. Sending account</p>
            {s.delivery === "google" ? (
              <div className="mt-2 space-y-2">
                <p className="flex items-center gap-1.5 text-sm text-success">
                  <CheckCircle2 className="size-4" /> Sending from {s.google_account}
                </p>
                <p className="text-xs text-muted">
                  Signed in with Google. NEXUS can only send mail as you; it cannot read your inbox.
                </p>
                <div className="flex flex-wrap gap-2">
                  {s.waiting > 0 && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={resend.isPending}
                      onClick={() => resend.mutate()}
                    >
                      <Send className="size-3.5" />{" "}
                      {resend.isPending ? "Sending…" : `Send ${s.waiting} waiting email${s.waiting === 1 ? "" : "s"}`}
                    </button>
                  )}
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => signOut.mutate()}>
                    Sign out of Google
                  </button>
                </div>
                {resend.data && (
                  <p className={cn("text-xs", resend.data.failed ? "text-danger" : "text-success")}>
                    Sent {resend.data.sent}
                    {resend.data.failed ? `; ${resend.data.failed} could not be sent yet` : ""}.
                  </p>
                )}
              </div>
            ) : s.google_ready ? (
              <div className="mt-2 space-y-3">
                <p className="text-xs text-muted">
                  Sign in once with the Google account that should send the emails. You sign in on Google&apos;s own
                  page: NEXUS never sees your password.
                </p>
                <button
                  type="button"
                  onClick={() => signIn.mutate()}
                  disabled={signIn.isPending}
                  className="inline-flex items-center gap-2.5 rounded-lg border border-[#dadce0] bg-white px-4 py-2 text-sm font-medium text-[#3c4043] shadow-sm transition-transform hover:-translate-y-0.5 hover:bg-[#f8f9fa]"
                >
                  <GoogleG /> {signIn.isPending ? "Opening Google…" : "Sign in with Google"}
                </button>
              </div>
            ) : (
              <SetupSteps onSaved={onSaved} />
            )}
          </div>

          <div className="space-y-3 rounded-xl border border-border p-4">
            <p className="text-sm font-semibold text-text">2. Your email</p>
            <label className="block text-xs text-muted">
              Used when a prompt says “email me”, and for approval requests
              <div className="mt-1 flex gap-2">
                <input
                  type="text"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  className={cn(field, "min-w-0 flex-1")}
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
            <label className="flex items-center gap-2 text-xs text-muted">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={(e) => save.mutate({ to: s.to ?? to, enabled: e.target.checked })}
                aria-label="Email every mission"
              />
              Also email every mission to this address, even when the prompt does not ask
            </label>
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
                <span className={cn("text-xs", test.data.status === "sent" ? "text-success" : "text-danger")}>
                  {test.data.status === "sent"
                    ? `Sent. Check ${s.to}.`
                    : (test.data.error ?? "Not sent; kept in the outbox.")}
                </span>
              )}
            </div>
            {s.delivery === "mailpit" && (
              <p className="text-xs text-warning">Not signed in to Google yet, so emails stay in the local outbox.</p>
            )}
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error.message}</p>}
    </section>
  );
}
