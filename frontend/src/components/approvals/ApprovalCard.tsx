"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { post } from "@/lib/api";
import { sounds } from "@/lib/sound";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";
import type { Approval } from "@/lib/queries";
import { DiffView } from "./DiffView";
import { RiskMeter } from "./RiskMeter";

interface Risk {
  level: string;
  score: number;
  factors: Record<string, number>;
  route: string;
  explanation: string;
}
interface Verdict {
  winner: string;
  winner_label: string;
  runner_up: string | null;
  confidence: number;
  dissent: string;
  reasoning?: string;
}
interface Evidence {
  kind: string;
  title: string;
  content: string;
}

type Decision = "approve" | "reject" | "edit" | "respond";

const KIND_LABEL: Record<string, string> = {
  approve_action: "Action approval",
  approve_team: "Team approval",
  answer_question: "Question for you",
  edit_plan: "Plan review",
};

/** The holographic APPROVED stamp that slams onto the card on approval. */
function Stamp() {
  return (
    <motion.div
      initial={{ scale: 3.2, rotate: -28, opacity: 0 }}
      animate={{ scale: 1, rotate: -12, opacity: 1 }}
      transition={{ type: "spring", stiffness: 520, damping: 18 }}
      className="pointer-events-none absolute top-6 right-8 z-10 grid place-items-center rounded-lg border-[3px] border-[var(--jade)] bg-[var(--jade)]/10 px-4 py-2 font-display text-2xl leading-none font-bold tracking-[0.2em] text-[var(--jade)] shadow-[0_0_30px_rgba(63,209,139,0.5)]"
      style={{ textShadow: "0 0 8px rgba(63,209,139,0.8)" }}
    >
      <span>APPROVED</span>
    </motion.div>
  );
}

export function ApprovalCard({ approval }: { approval: Approval }) {
  const qc = useQueryClient();
  const controls = useAnimationControls();
  const [mode, setMode] = useState<Decision | null>(null);
  const [text, setText] = useState("");
  const [stamped, setStamped] = useState(false);
  const [torn, setTorn] = useState(false);
  const p = approval.payload as Record<string, unknown>;
  const risk = p.risk as Risk | undefined;
  const verdict = p.verdict as Verdict | undefined;
  const evidence = (p.evidence as Evidence[] | undefined) ?? [];
  const action = p.action as Record<string, unknown> | undefined;
  const dryRun = p.dry_run as { ok: boolean; summary: string } | null | undefined;
  const requiresOverride = Boolean(p.requires_override);
  const [editJson, setEditJson] = useState(() =>
    JSON.stringify(approval.kind === "approve_team" ? { plan: p.plan, team: p.team } : (action ?? {}), null, 2),
  );

  const decide = useMutation({
    mutationFn: (body: Record<string, unknown>) => post(`/approvals/${approval.id}/decide`, body as never),
    onSuccess: async (_, body) => {
      if (body.decision === "approve" || body.decision === "edit") {
        setStamped(true);
        if (useUi.getState().soundOn) sounds.confirm();
        await controls.start({ x: [0, -6, 6, -3, 0], transition: { duration: 0.35, delay: 0.15 } });
      } else if (body.decision === "reject") {
        setTorn(true);
      }
      setTimeout(() => {
        void qc.invalidateQueries({ queryKey: ["approvals"] });
        void qc.invalidateQueries({ queryKey: ["missions"] });
      }, 1400);
    },
  });

  function submit(decision: Decision) {
    const body: Record<string, unknown> = { decision, by: "owner", channel: "ui" };
    if (decision === "reject") body.reason = text || "rejected in the UI";
    if (decision === "respond") body.response = text;
    if (decision === "approve" && requiresOverride) body.reason = `override: ${text || "approved by owner"}`;
    if (decision === "edit") {
      try {
        body.edited = JSON.parse(editJson);
      } catch {
        return;
      }
    }
    decide.mutate(body);
  }

  const halves = torn ? [0, 1] : [];
  return (
    <motion.article animate={controls} layout className="relative" aria-label={KIND_LABEL[approval.kind]}>
      <AnimatePresence>
        {torn &&
          halves.map((h) => (
            <motion.div
              key={h}
              initial={{ x: 0, rotate: 0, opacity: 1 }}
              animate={{ x: h ? 80 : -80, y: 40, rotate: h ? 14 : -14, opacity: 0 }}
              transition={{ duration: 1.1, ease: "easeIn" }}
              className="panel pointer-events-none absolute inset-y-0 z-10 w-1/2"
              style={{
                left: h ? "50%" : 0,
                clipPath: h
                  ? "polygon(4% 0,100% 0,100% 100%,0 100%,6% 60%,0 30%)"
                  : "polygon(0 0,100% 0,96% 30%,100% 60%,94% 100%,0 100%)",
              }}
            />
          ))}
      </AnimatePresence>
      <div className={cn("panel overflow-hidden p-4 transition-opacity", torn && "opacity-0")}>
        {stamped && <Stamp />}
        <header className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] tracking-wider text-faint uppercase">
              {KIND_LABEL[approval.kind] ?? approval.kind}
            </p>
            <h3 className="font-display text-lg text-text">{String(p.summary ?? "")}</h3>
            <p className="mt-0.5 text-xs text-muted">
              <Link href={`/missions?m=${approval.mission_id}`} className="underline decoration-border hover:text-text">
                mission {approval.mission_id}
              </Link>
              {" · "}
              {new Date(approval.created_at * 1000).toLocaleString()}
              {approval.email_status && (
                <span className="chip ml-2">
                  ✉ email {approval.email_status === "sent" ? "sent to Mailpit" : "in outbox (SMTP down)"}
                </span>
              )}
            </p>
          </div>
          {risk && <RiskMeter score={risk.score} level={risk.level} />}
        </header>

        {requiresOverride && (
          <p className="mt-3 rounded-lg border border-danger bg-danger/10 px-3 py-2 text-xs text-text">
            CRITICAL risk — blocked by policy unless you explicitly override (write a reason).
          </p>
        )}

        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {risk && (
            <section>
              <h4 className="mb-1 text-[11px] tracking-wider text-faint uppercase">Why this risk level</h4>
              <ul className="space-y-0.5 text-xs">
                {Object.entries(risk.factors).map(([k, v]) => (
                  <li key={k} className="flex items-center gap-2">
                    <span className="w-40 truncate text-muted">{k.replace(/_/g, " ")}</span>
                    <span className="h-1.5 flex-1 rounded-full bg-white/5">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.min(100, Math.abs(v) * 250)}%`,
                          background: v >= 0 ? "var(--ember)" : "var(--success)",
                        }}
                      />
                    </span>
                    <span className="w-12 text-right font-mono text-faint">
                      {v >= 0 ? "+" : ""}
                      {v.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-[11px] text-faint">{risk.explanation}</p>
            </section>
          )}
          {verdict && (
            <section>
              <h4 className="mb-1 text-[11px] tracking-wider text-faint uppercase">Tournament verdict</h4>
              <p className="text-sm text-text">
                {verdict.winner_label} <span className="text-muted">({verdict.winner})</span> · confidence{" "}
                <span className="font-mono">{verdict.confidence}</span>
              </p>
              {verdict.reasoning && <p className="mt-1 text-xs text-muted">{verdict.reasoning}</p>}
              <p className="mt-1 text-xs text-faint">Dissent: {verdict.dissent}</p>
            </section>
          )}
          {approval.kind === "approve_team" && (
            <section className="lg:col-span-2">
              <h4 className="mb-1 text-[11px] tracking-wider text-faint uppercase">Proposed team & plan</h4>
              <ul className="flex flex-wrap gap-1.5">
                {((p.team as { members?: { agent_id: string; step_ids: string[] }[] })?.members ?? []).map((m) => (
                  <li key={m.agent_id} className="chip">
                    {m.agent_id} → {m.step_ids.join(", ")}
                  </li>
                ))}
              </ul>
              <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-xs text-muted">
                {((p.plan as { steps?: { id: string; title: string; role: string }[] })?.steps ?? []).map((s) => (
                  <li key={s.id}>
                    {s.title} <span className="text-faint">({s.role})</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
          {approval.kind === "answer_question" && (
            <p className="text-sm text-text lg:col-span-2">{String(p.question ?? "")}</p>
          )}
        </div>

        {dryRun && (
          <p
            className={cn(
              "mt-3 rounded-lg px-3 py-1.5 text-xs",
              dryRun.ok ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
            )}
          >
            Dry run {dryRun.ok ? "passed" : "failed"} — {dryRun.summary}
          </p>
        )}

        {evidence.length > 0 && (
          <details className="mt-3" open={evidence.some((e) => e.kind === "diff")}>
            <summary className="cursor-pointer text-[11px] tracking-wider text-faint uppercase">
              Evidence ({evidence.length})
            </summary>
            <div className="mt-2 space-y-2">
              {evidence.map((e, i) => (
                <div key={i}>
                  <p className="mb-1 text-xs text-gold">{e.title}</p>
                  <DiffView text={e.content} />
                </div>
              ))}
            </div>
          </details>
        )}

        {mode === "edit" && (
          <textarea
            value={editJson}
            onChange={(e) => setEditJson(e.target.value)}
            rows={10}
            className="mt-3 w-full rounded-lg border border-border bg-black/50 p-2 font-mono text-[11px]"
            aria-label="Edit payload as JSON"
          />
        )}
        {(mode === "reject" || mode === "respond" || requiresOverride || approval.kind === "answer_question") && (
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              approval.kind === "answer_question"
                ? "Your answer"
                : mode === "respond"
                  ? "Feedback for the planner"
                  : requiresOverride
                    ? "Override reason"
                    : "Reason (optional)"
            }
            className="mt-3 w-full rounded-lg border border-border bg-black/40 px-3 py-2 text-sm"
          />
        )}

        <footer className="mt-4 flex flex-wrap gap-2">
          {approval.kind === "answer_question" ? (
            <button
              type="button"
              disabled={!text || decide.isPending}
              onClick={() => submit("respond")}
              className="rounded-lg bg-accent/20 px-4 py-2 text-sm font-semibold text-accent ring-1 ring-accent/60 disabled:opacity-40"
            >
              Answer
            </button>
          ) : (
            <>
              <button
                type="button"
                disabled={decide.isPending || (requiresOverride && !text)}
                onClick={() => submit("approve")}
                className="rounded-lg bg-[#1e5e3f] px-4 py-2 text-sm font-semibold text-white ring-1 ring-success/60 hover:bg-[#237049] disabled:opacity-40"
              >
                {requiresOverride ? "Override & approve" : "Approve"}
              </button>
              <button
                type="button"
                disabled={decide.isPending}
                onClick={() => (mode === "reject" ? submit("reject") : setMode("reject"))}
                className="rounded-lg bg-[#5c120f] px-4 py-2 text-sm font-semibold text-white ring-1 ring-danger/60 hover:bg-[#71170f]"
              >
                {mode === "reject" ? "Confirm reject" : "Reject"}
              </button>
              <button
                type="button"
                onClick={() => (mode === "edit" ? submit("edit") : setMode("edit"))}
                className="chip cursor-pointer px-3 py-2 hover:text-text"
              >
                {mode === "edit" ? "Apply edit & approve" : "Edit"}
              </button>
              <button
                type="button"
                onClick={() => (mode === "respond" ? submit("respond") : setMode("respond"))}
                className="chip cursor-pointer px-3 py-2 hover:text-text"
              >
                {mode === "respond" ? "Send feedback (replan)" : "Respond"}
              </button>
            </>
          )}
        </footer>
        {decide.isError && <p className="mt-2 text-xs text-danger">{decide.error.message}</p>}
      </div>
    </motion.article>
  );
}
