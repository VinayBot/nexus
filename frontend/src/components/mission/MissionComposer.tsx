"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, Send, X } from "lucide-react";
import { useRef, useState } from "react";
import { API_URL } from "@/lib/config";
import { post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { usePlaybooks, useTickets, type Mission } from "@/lib/queries";

interface Doc {
  name: string;
  text: string;
}

const EXAMPLES: Record<string, string> = {
  "": "What is the difference between ReAct and Plan-and-Execute agents?",
  council_qa: "When should a team prefer optimistic over pessimistic locking?",
  self_healing: "The demo-service is unhealthy. Investigate, fix and verify it.",
  ticket_solver: "Solve ticket T-101",
  project_builder: "Build a small FastAPI API to manage books (title, author, year) with tests.",
  dynamic: "Review the demo-service code for risky error handling and summarise the top 3 issues.",
};

export function MissionComposer({ onCreated }: { onCreated: (m: Mission) => void }) {
  const qc = useQueryClient();
  const playbooks = usePlaybooks();
  const tickets = useTickets();
  const [task, setTask] = useState("");
  const [playbook, setPlaybook] = useState("");
  const [ticket, setTicket] = useState("T-101");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const create = useMutation({
    mutationFn: () => {
      const inputs: Record<string, unknown> = {};
      if (playbook === "ticket_solver") inputs.ticket_id = ticket;
      if (docs.length) inputs.docs = docs;
      const text =
        task.trim() || (playbook === "ticket_solver" ? `Solve ticket ${ticket}` : (EXAMPLES[playbook] ?? ""));
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
    const res = await fetch(`${API_URL}/api/v1/uploads/parse`, { method: "POST", body: form });
    if (!res.ok) {
      setUploadError((await res.json().catch(() => ({ detail: res.statusText }))).detail);
      return;
    }
    const doc = (await res.json()) as Doc;
    setDocs((d) => [...d, doc]);
  }

  const chosen = playbooks.data?.find((p) => p.id === playbook);
  return (
    <form
      className="panel space-y-2.5 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <h2 className="panel-title text-sm text-gold">New mission</h2>
      <label className="block">
        <span className="sr-only">Playbook</span>
        <select
          value={playbook}
          onChange={(e) => setPlaybook(e.target.value)}
          className="w-full rounded-lg border border-border bg-black/40 px-2.5 py-2 text-sm text-text"
        >
          <option value="">Let the Commander decide</option>
          {playbooks.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      {chosen && <p className="text-[11px] leading-snug text-muted">{chosen.description}</p>}
      {playbook === "ticket_solver" && (
        <select
          value={ticket}
          onChange={(e) => setTicket(e.target.value)}
          className="w-full rounded-lg border border-border bg-black/40 px-2.5 py-2 text-sm"
        >
          {tickets.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.id} · {t.title} ({t.status})
            </option>
          ))}
        </select>
      )}
      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        rows={4}
        placeholder={playbook === "ticket_solver" ? `Solve ticket ${ticket}` : EXAMPLES[playbook]}
        className="w-full resize-none rounded-lg border border-border bg-black/40 px-2.5 py-2 text-sm text-text placeholder:text-faint"
        aria-label="Task"
      />
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
          <p className="text-[11px] text-faint">Scope: small services only (≤ 8 files) — local 3–8B models.</p>
        </div>
      )}
      <button
        type="submit"
        disabled={create.isPending}
        className={cn("btn btn-primary w-full", create.isPending && "animate-pulse")}
      >
        <Send className="size-4" /> {create.isPending ? "Deploying the squad…" : "Begin mission"}
      </button>
      {create.isError && <p className="text-xs text-danger">{String(create.error.message)}</p>}
    </form>
  );
}
