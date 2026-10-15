"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { API_URL } from "@/lib/config";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useActiveMission } from "@/stores/missions";
import { useTour } from "@/stores/tour";
import { create } from "zustand";

interface Msg {
  role: "user" | "assistant";
  text: string;
  sources?: string[];
  actions?: Action[];
}
interface Action {
  type: "navigate" | "spotlight" | "tour" | "start_demo";
  path?: string;
  element?: string;
  label?: string;
}

/** Lets other components (command palette) open Hikari with a question. */
export const useHikari = create<{
  open: boolean;
  pending: string | null;
  ask: (q: string) => void;
  setOpen: (o: boolean) => void;
}>()((set) => ({
  open: false,
  pending: null,
  ask: (q) => set({ open: true, pending: q }),
  setOpen: (open) => set({ open }),
}));

/** Read an SSE response body (POST) as {event, data} pairs. */
async function* sse(res: Response): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.search(/\r?\n\r?\n/)) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i).replace(/^\r?\n\r?\n/, "");
      let event = "message";
      let data = "";
      for (const line of chunk.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) yield { event, data: JSON.parse(data) as Record<string, unknown> };
    }
  }
}

function HikariBot({ eyes }: { eyes: { x: number; y: number } }) {
  return (
    <svg viewBox="0 0 60 64" className="size-14 drop-shadow-[0_0_14px_rgba(79,227,240,0.7)]" aria-hidden>
      <ellipse cx={30} cy={60} rx={12} ry={2.5} fill="black" opacity={0.3} />
      <rect x={14} y={38} width={32} height={18} rx={9} fill="#f5f2ec" />
      <rect x={6} y={6} width={48} height={36} rx={18} fill="#f5f2ec" />
      <path d="M8,15 C20,9 40,9 52,15 L52,19 C40,13 20,13 8,19 Z" fill="#4fe3f0" />
      <rect x={12} y={15} width={36} height={21} rx={10} fill="#0e1116" />
      <circle cx={23 + eyes.x} cy={25.5 + eyes.y} r={3.6} fill="#4fe3f0" />
      <circle cx={37 + eyes.x} cy={25.5 + eyes.y} r={3.6} fill="#4fe3f0" />
      <circle cx={30} cy={46} r={2.4} fill="#4fe3f0" />
    </svg>
  );
}

export function Hikari() {
  const { open, setOpen, pending } = useHikari();
  const router = useRouter();
  const mission = useActiveMission((s) => s.activeId);
  const tour = useTour();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conv, setConv] = useState<string | null>(null);
  const [eyes, setEyes] = useState({ x: 0, y: 0 });
  const box = useRef<HTMLDivElement>(null);
  const bot = useRef<HTMLButtonElement>(null);
  const suggestions = useQuery({
    queryKey: ["guide-suggestions"],
    queryFn: () => get<string[]>("/guide/suggestions"),
    staleTime: Infinity,
  });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const r = bot.current?.getBoundingClientRect();
      if (!r) return;
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      const d = Math.max(1, Math.hypot(dx, dy));
      setEyes({ x: (dx / d) * 2.2, y: (dy / d) * 1.6 });
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, []);
  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight });
  }, [msgs]);

  async function run(actions: Action[]) {
    for (const a of actions) {
      if (a.type === "navigate" && a.path) router.push(a.path);
      if (a.type === "spotlight" && a.element) setTimeout(() => tour.flash(a.element!), 700);
      if (a.type === "tour") {
        setOpen(false);
        tour.start();
      }
      if (a.type === "start_demo") {
        const m = await post<{ id: string }>("/missions", {
          task: "What is the difference between ReAct and Plan-and-Execute agents?",
          playbook: "council_qa",
        });
        useActiveMission.getState().setActive(m.id);
        router.push(`/dojo?m=${m.id}`);
      }
    }
  }

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }, { role: "assistant", text: "" }]);
    try {
      const res = await fetch(`${API_URL}/api/v1/guide/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question, conversation_id: conv, mission_id: mission }),
      });
      for await (const { event, data } of sse(res)) {
        if (event === "meta") setConv(String(data.conversation_id));
        if (event === "actions") {
          const actions = (data.actions as Action[]) ?? [];
          setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, actions } : x)));
          void run(actions);
        }
        if (event === "token")
          setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, text: x.text + String(data.text) } : x)));
        if (event === "done")
          setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, sources: data.sources as string[] } : x)));
      }
    } catch {
      setMsgs((m) =>
        m.map((x, i) => (i === m.length - 1 ? { ...x, text: "I can't reach the backend right now." } : x)),
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (pending) {
      useHikari.setState({ pending: null });
      void ask(pending);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  return (
    <>
      <button
        ref={bot}
        type="button"
        onClick={() => setOpen(!open)}
        className="fixed right-5 bottom-5 z-50 size-16"
        aria-label={open ? "Close Hikari the guide" : "Ask Hikari the guide"}
        aria-expanded={open}
      >
        <motion.span
          className="block"
          animate={{ y: [0, -5, 0] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        >
          <HikariBot eyes={eyes} />
        </motion.span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.section
            initial={{ opacity: 0, y: 30, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30 }}
            className="panel fixed right-5 bottom-24 z-50 flex h-[min(560px,70vh)] w-[min(400px,92vw)] flex-col"
            aria-label="Hikari chat"
          >
            <header className="border-b border-border/50 px-3 py-2">
              <p className="font-display text-base text-accent">Hikari</p>
              <p className="text-[10.5px] text-faint">
                Guide · answers from NEXUS docs + live state · can navigate, spotlight, tour and start demo missions
              </p>
            </header>
            <div ref={box} className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 text-sm">
              {msgs.length === 0 && (
                <p className="text-xs text-muted">
                  Hi! I&apos;m Hikari. Ask me how anything works, what a robot is doing, or let me give you the tour.
                </p>
              )}
              {msgs.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    "rounded-xl px-3 py-2",
                    m.role === "user" ? "ml-8 bg-accent/10 text-text" : "mr-4 bg-black/30",
                  )}
                >
                  {m.role === "assistant" ? (
                    <div className="text-[13px] leading-relaxed [&_code]:font-mono [&_p]:mb-1">
                      <ReactMarkdown>{m.text || (busy && i === msgs.length - 1 ? "…" : "")}</ReactMarkdown>
                    </div>
                  ) : (
                    m.text
                  )}
                  {m.actions?.map(
                    (a, j) =>
                      a.label && (
                        <button
                          key={j}
                          type="button"
                          onClick={() => void run([a])}
                          className="chip mt-1 mr-1 cursor-pointer border-accent/60 text-accent"
                        >
                          ↪ {a.label}
                        </button>
                      ),
                  )}
                  {m.sources && m.sources.length > 0 && (
                    <p className="mt-1 text-[10px] text-faint">
                      from: {[...new Set(m.sources)].join(" · ")} · live state
                    </p>
                  )}
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-1 px-3 pb-1">
              {suggestions.data?.slice(0, 4).map((s) => (
                <button key={s} type="button" onClick={() => void ask(s)} className="chip cursor-pointer text-[10.5px]">
                  {s}
                </button>
              ))}
            </div>
            <form
              className="flex gap-2 border-t border-border/50 p-2"
              onSubmit={(e) => {
                e.preventDefault();
                void ask(input);
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask Hikari…"
                className="min-w-0 flex-1 rounded-lg border border-border bg-black/40 px-3 py-2 text-sm"
                aria-label="Message Hikari"
              />
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-accent/20 px-3 text-sm text-accent ring-1 ring-accent/50 disabled:opacity-40"
              >
                Ask
              </button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>
    </>
  );
}
