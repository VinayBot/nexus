"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { FileUp, Send, X } from "lucide-react";
import { useRef, useState } from "react";
import { API_URL } from "@/lib/config";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useCan } from "@/lib/me";
import { MISSION_TYPES } from "@/lib/playbooks";
import { EmailIntentHint } from "./EmailIntentHint";
import { useTickets, type Mission } from "@/lib/queries";

interface Doc {
  name: string;
  text: string;
}

/** Task first, then an optional mission type. An empty box runs the type's example. */
export function MissionComposer({ onCreated }: { onCreated: (m: Mission) => void }) {
  const qc = useQueryClient();
  const tickets = useTickets();
  const [task, setTask] = useState("");
  const [playbook, setPlaybook] = useState("");
  const [ticket, setTicket] = useState("T-101");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const chosen = MISSION_TYPES.find((t) => t.id === playbook) ?? MISSION_TYPES[0]!;

  const canRun = useCan("operator");
  const create = useMutation({
    mutationFn: () => {
      const inputs: Record<string, unknown> = {};
      if (playbook === "ticket_solver") inputs.ticket_id = ticket;
      if (docs.length) inputs.docs = docs;
      const text = task.trim() || (playbook === "ticket_solver" ? `Solve ticket ${ticket}` : chosen.example);
      return post<Mission>("/missions", { task: text, playbook: playbook || null, inputs } as never);
    },
    onSuccess: (m) => {
      setTask("");
      setDocs([]);
      void qc.invalidateQueries({ queryKey: ["missions"] });
      onCreated(m);
    },
  });

  async function upload(f: File) {
    setUploadError(null);
    const form = new FormData();
    form.append("file", f);
    const res = await fetch(`${API_URL}/api/v1/uploads/parse`, {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!res.ok) {
      setUploadError((await res.json().catch(() => ({ detail: res.statusText }))).detail);
      return;
    }
    const doc = (await res.json()) as Doc;
    setDocs((d) => [...d, doc]);
  }

  return (
    <form
      data-tour="new-mission"
      className="panel space-y-3 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <h2 className="panel-title text-sm">New mission</h2>
      <div className="focus-glow">
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && task.trim()) create.mutate();
          }}
          rows={4}
          className="w-full resize-none rounded-lg border border-border bg-black/25 px-3 py-2.5 text-sm text-text placeholder:text-faint"
          aria-label="What should the agents do?"
        />
      </div>
      <EmailIntentHint task={task} />
      <div>
        <p className="mb-1.5 text-xs text-faint">Mission type</p>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Mission type">
          {MISSION_TYPES.map((t) => {
            const Icon = t.icon;
            const on = t.id === playbook;
            return (
              <button
                key={t.id || "auto"}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPlaybook(t.id)}
                className={cn(
                  "relative inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
                  on
                    ? "border-transparent text-white"
                    : "border-border text-muted hover:border-white/20 hover:text-text",
                )}
              >
                {on && (
                  <motion.span
                    layoutId="mission-type"
                    className="absolute inset-0 rounded-full bg-[var(--accent-strong)]"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <Icon className="relative size-3.5" aria-hidden />
                <span className="relative">{t.label}</span>
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-xs leading-snug text-muted">{chosen.hint}</p>
      </div>
      {playbook === "ticket_solver" && (
        <select
          value={ticket}
          onChange={(e) => setTicket(e.target.value)}
          className="w-full rounded-lg border border-border bg-black/25 px-2.5 py-2 text-sm"
          aria-label="Ticket"
        >
          {tickets.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.id} · {t.title} ({t.status})
            </option>
          ))}
        </select>
      )}
      {playbook === "project_builder" && (
        <div className="space-y-1">
          <button type="button" onClick={() => file.current?.click()} className="chip cursor-pointer">
            <FileUp className="size-3" /> Attach requirements (.md, .txt, .pdf)
          </button>
          <input
            ref={file}
            type="file"
            accept=".md,.txt,.pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])}
          />
          {docs.map((d, i) => (
            <span key={i} className="chip mr-1">
              {d.name} · {d.text.length.toLocaleString()} chars
              <button
                type="button"
                aria-label={`Remove ${d.name}`}
                onClick={() => setDocs((x) => x.filter((_, j) => j !== i))}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
          {uploadError && <p className="text-xs text-danger">{uploadError}</p>}
        </div>
      )}
      <button
        type="submit"
        disabled={!canRun || create.isPending || (!task.trim() && playbook !== "ticket_solver")}
        title={canRun ? undefined : "Viewers can watch missions; an operator or owner starts them."}
        className={cn("btn btn-primary w-full", create.isPending && "animate-pulse")}
      >
        <Send className="size-4" /> {create.isPending ? "Starting…" : "Start mission"}
      </button>
      {create.isError && <p className="text-xs text-danger">{String(create.error.message)}</p>}
    </form>
  );
}
