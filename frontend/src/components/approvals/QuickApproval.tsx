"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, ExternalLink, FileText, ShieldAlert, X } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { useState } from "react";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Approval } from "@/lib/queries";
import { sounds } from "@/lib/sound";
import { useCan } from "@/lib/me";
import { useUi } from "@/stores/ui";
import { DiffView } from "./DiffView";

interface Risk {
  level: string;
  score: number;
  explanation: string;
}
interface Evidence {
  kind: string;
  title: string;
  content: string;
}

export const KIND_LABEL: Record<string, string> = {
  approve_action: "Approve this action?",
  approve_team: "Approve this team?",
  answer_question: "The agents have a question",
  edit_plan: "Review this plan",
};

const LEVEL_STYLE: Record<string, string> = {
  LOW: "bg-success/15 text-success",
  MEDIUM: "bg-warning/15 text-warning",
  HIGH: "bg-[rgb(251_146_60/0.15)] text-[rgb(251_146_60)]",
  CRITICAL: "bg-danger/15 text-danger",
};

/**
 * A compact approval: what will happen, how risky it is, the key evidence, and the
 * decision buttons. Used by the global pop-up and inline in Mission Control; the
 * Approvals page keeps the full card with every risk factor.
 */
export function QuickApproval({ approval, onDone }: { approval: Approval; onDone?: () => void }) {
  const qc = useQueryClient();
  const p = approval.payload as Record<string, unknown>;
  const risk = p.risk as Risk | undefined;
  const action = p.action as { summary?: string; files_touched?: string[]; target?: string } | undefined;
  const dryRun = p.dry_run as { ok: boolean; summary: string } | null | undefined;
  const evidence = (p.evidence as Evidence[] | undefined) ?? [];
  const answer = typeof p.answer === "string" ? p.answer : "";
  const requiresOverride = Boolean(p.requires_override);
  const question = approval.kind === "answer_question";
  const [text, setText] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [done, setDone] = useState<"approved" | "rejected" | "answered" | null>(null);
  const diff = evidence.find((e) => e.kind === "diff");
  const team = (p.team as { members?: { agent_id: string; step_ids: string[] }[] } | undefined)?.members;

  const canDecide = useCan("operator");
  const decide = useMutation({
    mutationFn: (body: Record<string, unknown>) => post(`/approvals/${approval.id}/decide`, body as never),
    onSuccess: (_, body) => {
      setDone(body.decision === "approve" ? "approved" : body.decision === "reject" ? "rejected" : "answered");
      if (useUi.getState().soundOn) sounds.confirm();
      setTimeout(() => {
        void qc.invalidateQueries({ queryKey: ["approvals"] });
        void qc.invalidateQueries({ queryKey: ["missions"] });
        onDone?.();
      }, 900);
    },
  });

  function submit(decision: "approve" | "reject" | "respond") {
    const body: Record<string, unknown> = { decision, by: "owner", channel: "ui" };
    if (decision === "reject") body.reason = text || "rejected in the UI";
    if (decision === "respond") body.response = text;
    if (decision === "approve" && requiresOverride) body.reason = `override: ${text || "approved by owner"}`;
    decide.mutate(body);
  }

  if (done) {
    return (
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="grid place-items-center gap-2 py-8 text-center"
        role="status"
      >
        <motion.span
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 420, damping: 16 }}
          className={cn(
            "grid size-12 place-items-center rounded-full",
            done === "rejected" ? "bg-danger/20 text-danger" : "bg-success/20 text-success",
          )}
        >
          {done === "rejected" ? <X className="size-6" /> : <Check className="size-6" />}
        </motion.span>
        <p className="text-sm text-text">
          {done === "approved"
            ? "Approved. The agents are continuing."
            : done === "rejected"
              ? "Rejected. Nothing was changed."
              : "Answer sent."}
        </p>
      </motion.div>
    );
  }

  return (
    <div className="space-y-3" aria-label={KIND_LABEL[approval.kind]}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-[rgb(var(--accent-rgb)/0.15)] text-accent">
          {question ? <FileText className="size-4.5" /> : <ShieldAlert className="size-4.5" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-faint">{KIND_LABEL[approval.kind] ?? approval.kind}</p>
          <h3 className="text-base leading-snug font-semibold text-text">
            {String(question ? (p.question ?? p.summary ?? "") : (p.summary ?? ""))}
          </h3>
          <p className="mt-0.5 text-xs text-muted">
            Mission{" "}
            <Link href={`/missions?m=${approval.mission_id}`} className="underline decoration-border hover:text-text">
              {approval.mission_id}
            </Link>
            {action?.files_touched?.length ? ` · ${action.files_touched.join(", ")}` : ""}
          </p>
        </div>
        {risk && (
          <span
            className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold", LEVEL_STYLE[risk.level])}
            title={risk.explanation}
          >
            {risk.level} risk
          </span>
        )}
      </div>

      {requiresOverride && (
        <p className="rounded-lg bg-danger/10 px-3 py-2 text-xs text-text">
          Critical risk: blocked by policy unless you override it with a reason.
        </p>
      )}
      {dryRun && (
        <p
          className={cn(
            "rounded-lg px-3 py-2 text-xs",
            dryRun.ok ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
          )}
        >
          Rehearsal {dryRun.ok ? "passed" : "failed"}: {dryRun.summary}
        </p>
      )}
      {team && (
        <ul className="flex flex-wrap gap-1.5">
          {team.map((m) => (
            <li key={m.agent_id} className="chip capitalize">
              {m.agent_id}: {m.step_ids.length} step{m.step_ids.length === 1 ? "" : "s"}
            </li>
          ))}
        </ul>
      )}
      {diff ? (
        <div className="max-h-48 overflow-auto rounded-lg">
          <DiffView text={diff.content} />
        </div>
      ) : (
        answer && (
          <div className="prose-sm max-h-48 overflow-y-auto rounded-lg border border-border bg-black/20 px-3 py-2 text-sm leading-relaxed text-muted [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-text [&_h2]:mt-2 [&_h2]:font-semibold [&_h2]:text-text">
            <ReactMarkdown>{answer.slice(0, 1600)}</ReactMarkdown>
          </div>
        )
      )}

      {(question || rejecting || requiresOverride) && (
        <input
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            question ? "Your answer" : requiresOverride && !rejecting ? "Override reason" : "Reason (optional)"
          }
          className="w-full rounded-lg border border-border bg-black/30 px-3 py-2 text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && question && text) submit("respond");
          }}
        />
      )}

      {!canDecide && <p className="text-xs text-muted">Viewers can read this; an operator or owner decides.</p>}
      <fieldset disabled={!canDecide} className="flex flex-wrap items-center gap-2">
        {question ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!text || decide.isPending}
            onClick={() => submit("respond")}
          >
            Send answer
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-success"
              disabled={decide.isPending || (requiresOverride && !text)}
              onClick={() => submit("approve")}
            >
              <Check className="size-4" /> {requiresOverride ? "Override and approve" : "Approve"}
            </button>
            <button
              type="button"
              className={cn("btn", rejecting ? "btn-danger" : "btn-ghost")}
              disabled={decide.isPending}
              onClick={() => (rejecting ? submit("reject") : setRejecting(true))}
            >
              <X className="size-4" /> {rejecting ? "Confirm reject" : "Reject"}
            </button>
          </>
        )}
        <Link href="/approvals" className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          Full details <ExternalLink className="size-3" />
        </Link>
      </fieldset>
      {decide.isError && <p className="text-xs text-danger">{decide.error.message}</p>}
    </div>
  );
}
