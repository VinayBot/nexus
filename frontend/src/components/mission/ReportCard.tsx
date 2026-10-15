"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download } from "lucide-react";
import { API_URL } from "@/lib/config";
import type { Mission } from "@/lib/queries";

interface Report {
  title?: string;
  outcome?: string;
  summary?: string;
  answer?: string | null;
  highlights?: string[];
  tokens?: number;
  duration_s?: number;
  download?: string | null;
  diff?: string | null;
}

export function ReportCard({ mission }: { mission: Mission }) {
  const r = (mission.report ?? {}) as Report;
  const ok = r.outcome === "success";
  return (
    <details className="panel group px-3 py-2" open={ok}>
      <summary className="flex cursor-pointer list-none items-center gap-2">
        <span className="size-2 rounded-full" style={{ background: ok ? "var(--success)" : "var(--warning)" }} />
        <span className="panel-title text-sm text-gold">Report</span>
        <span className="text-xs text-muted">{r.summary}</span>
        <span className="ml-auto font-mono text-[10.5px] text-faint">
          {(r.tokens ?? mission.tokens).toLocaleString()} tokens{r.duration_s ? ` · ${r.duration_s}s` : ""}
        </span>
      </summary>
      <div className="mt-2 grid gap-3 md:grid-cols-[minmax(0,1fr)_260px]">
        <div className="prose-sm max-h-40 overflow-y-auto text-sm leading-relaxed text-text [&_code]:font-mono [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-black/40 [&_pre]:p-2">
          {r.answer ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
          ) : (
            <p className="text-faint">No written answer for this mission.</p>
          )}
          {r.diff && <pre className="mt-2 text-[11px]">{r.diff}</pre>}
        </div>
        <ul className="max-h-40 space-y-1 overflow-y-auto pr-1 text-[11.5px] text-muted">
          {(r.highlights ?? []).map((h, i) => (
            <li key={i}>• {h}</li>
          ))}
          {r.download && (
            <li>
              <a href={`${API_URL}${r.download}`} className="chip mt-1 hover:text-text">
                <Download className="size-3" /> Download project
              </a>
            </li>
          )}
        </ul>
      </div>
    </details>
  );
}
