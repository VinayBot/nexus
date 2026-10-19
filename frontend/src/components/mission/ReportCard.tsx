"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "motion/react";
import { CheckCircle2, ChevronDown, Download, ExternalLink, Globe, XCircle, AlertTriangle } from "lucide-react";
import { useState } from "react";
import { API_URL } from "@/lib/config";
import { cn } from "@/lib/cn";
import type { Mission } from "@/lib/queries";
import { TicketBar } from "./TicketBar";

interface Report {
  title?: string;
  outcome?: string;
  summary?: string;
  answer?: string | null;
  highlights?: string[];
  tokens?: number;
  duration_s?: number;
  download?: string | null;
  preview_url?: string | null;
  files?: string[] | null;
  diff?: string | null;
  ticket_id?: string | null;
  emailed_to?: string | null;
}

/** What the outcome means, in one plain sentence per mission type. */
function plainOutcome(r: Report, playbook: string | null): string {
  if (r.outcome !== "success") return r.summary ?? "";
  if (r.preview_url) return "Your page was written, checked and published. Open it with the button below.";
  if (r.download) return "Your project was built, tested and packaged. Download it below.";
  if (playbook === "self_healing") return "The bug was fixed, verified on live traffic and saved to the Fix Library.";
  if (playbook === "ticket_solver") return "The ticket was solved and a comment with the fix was posted.";
  if (r.ticket_id)
    return `The ticket was written from the code and logs and filed as ${r.ticket_id}${r.emailed_to ? ", then emailed to you" : ""}.`;
  return "Here is the team's answer.";
}

const OUTCOME: Record<string, { label: string; tone: string; Icon: typeof CheckCircle2 }> = {
  success: { label: "Completed", tone: "text-success bg-success/12", Icon: CheckCircle2 },
  partial: { label: "Partly done", tone: "text-warning bg-warning/12", Icon: AlertTriangle },
  rejected: { label: "Rejected by you", tone: "text-muted bg-white/5", Icon: XCircle },
  blocked: { label: "Blocked by policy", tone: "text-danger bg-danger/12", Icon: XCircle },
  rolled_back: { label: "Rolled back", tone: "text-warning bg-warning/12", Icon: AlertTriangle },
};

/** The mission's result, shown first: the answer, the published page, the download. */
export function ReportCard({ mission }: { mission: Mission }) {
  const r = (mission.report ?? {}) as Report;
  const o = OUTCOME[r.outcome ?? ""] ?? OUTCOME.partial!;
  const [showPreview, setShowPreview] = useState(true);
  const [showSteps, setShowSteps] = useState(false);
  const steps = [...new Set(r.highlights ?? [])];
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="result-stagger panel overflow-hidden"
      aria-label="Mission result"
      data-testid="mission-result"
    >
      <div className="border-b border-border px-4 py-3">
        <p className="text-xs font-medium text-faint">You asked</p>
        <p className="mt-0.5 text-sm text-text">“{mission.task}”</p>
      </div>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 py-3">
        <span
          className={cn(
            "result-badge inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
            o.tone,
          )}
        >
          <o.Icon className="size-3.5" /> {o.label}
        </span>
        <p className="min-w-0 flex-1 text-sm text-muted">{plainOutcome(r, mission.playbook)}</p>
      </header>

      {r.ticket_id && <TicketBar ticketId={r.ticket_id} emailedTo={r.emailed_to} />}

      {(r.preview_url || r.download) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-[rgb(var(--accent-rgb)/0.06)] px-4 py-2.5">
          {r.preview_url && (
            <>
              <Globe className="size-4 text-accent" />
              <a
                href={r.preview_url}
                target="_blank"
                rel="noreferrer"
                className="truncate font-mono text-xs text-accent hover:underline"
              >
                {r.preview_url}
              </a>
              <a href={r.preview_url} target="_blank" rel="noreferrer" className="btn btn-primary btn-sm ml-auto">
                <ExternalLink className="size-3.5" /> Open page
              </a>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPreview((s) => !s)}>
                {showPreview ? "Hide preview" : "Preview"}
              </button>
            </>
          )}
          {r.download && (
            <a href={`${API_URL}${r.download}`} className="btn btn-primary btn-sm">
              <Download className="size-3.5" /> Download project (.zip)
            </a>
          )}
        </div>
      )}

      {r.preview_url && showPreview && (
        <iframe
          title="Published page preview"
          src={r.preview_url}
          sandbox=""
          className="h-[420px] w-full border-b border-border bg-white"
        />
      )}

      {r.files && r.files.length > 0 && !r.preview_url && (
        <div className="border-b border-border px-4 py-2.5">
          <p className="text-xs font-medium text-faint">Files</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {r.files.map((f) => (
              <li key={f} className="chip font-mono">
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="px-4 pt-3 text-xs font-medium text-faint">{r.preview_url ? "Page content" : "Output"}</p>
      <div className="max-h-[420px] overflow-y-auto px-4 pt-1 pb-3 text-sm leading-relaxed text-text [&_code]:font-mono [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1 [&_h2]:font-semibold [&_li]:ml-4 [&_li]:list-disc [&_p]:my-1.5 [&_p]:text-muted [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-black/40 [&_pre]:p-2">
        {r.answer ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
        ) : (
          <p className="text-faint">{r.summary || "This mission produced no written answer."}</p>
        )}
        {r.diff && <pre className="mt-2 text-[11px]">{r.diff}</pre>}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-4 py-2.5 text-xs text-muted">
        {steps.length > 0 && (
          <button
            type="button"
            onClick={() => setShowSteps((v) => !v)}
            className="flex items-center gap-1 hover:text-text"
            aria-expanded={showSteps}
          >
            <ChevronDown className={cn("size-3.5 transition-transform", showSteps && "rotate-180")} /> How the team did
            it
          </button>
        )}
        <span className="ml-auto font-mono text-[11px] text-faint">
          {r.duration_s ? `${Math.round(r.duration_s)} s · ` : ""}
          {(r.tokens ?? mission.tokens).toLocaleString()} tokens
        </span>
      </div>
      {showSteps && (
        <ol className="list-decimal space-y-0.5 border-t border-border px-4 py-2.5 pl-9 text-xs text-muted">
          {steps.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ol>
      )}
    </motion.section>
  );
}
