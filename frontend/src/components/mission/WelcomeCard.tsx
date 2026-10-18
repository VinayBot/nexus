"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { post } from "@/lib/api";
import { MISSION_TYPES } from "@/lib/playbooks";
import type { Mission } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";

const STEPS = [
  ["Describe the task", "Type what you want, or pick a mission type on the left."],
  ["Watch the team work", "Agents plan, research, write and test. Every step appears live."],
  ["Approve and get the result", "Risky actions wait for your OK, then the result appears here."],
];

/** Shown when no mission is selected: how it works, plus one-click starter missions. */
export function WelcomeCard() {
  const qc = useQueryClient();
  const router = useRouter();
  const setActive = useActiveMission((s) => s.setActive);
  const start = useMutation({
    mutationFn: (t: { id: string; example: string }) =>
      post<Mission>("/missions", { task: t.example, playbook: t.id || null, inputs: {} } as never),
    onSuccess: (m) => {
      void qc.invalidateQueries({ queryKey: ["missions"] });
      setActive(m.id);
      router.push(`/missions?m=${m.id}`);
    },
  });
  const starters = MISSION_TYPES.filter((t) =>
    ["web_builder", "council_qa", "self_healing", "project_builder"].includes(t.id),
  );
  return (
    <section className="panel p-6" aria-label="Welcome">
      <h1 className="text-2xl font-semibold tracking-tight text-text">What should the agents do?</h1>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        NEXUS runs a team of 14 AI agents on your Mac with local models. Nothing leaves your machine.
      </p>
      <ol className="mt-5 grid gap-3 md:grid-cols-3">
        {STEPS.map(([title, body], i) => (
          <motion.li
            key={title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 * i }}
            className="rounded-xl border border-border bg-white/[0.02] p-4"
          >
            <span className="grid size-7 place-items-center rounded-full bg-[rgb(99_102_241/0.18)] text-xs font-bold text-accent">
              {i + 1}
            </span>
            <p className="mt-2 text-sm font-semibold text-text">{title}</p>
            <p className="mt-0.5 text-xs text-muted">{body}</p>
          </motion.li>
        ))}
      </ol>
      <h2 className="mt-6 text-sm font-semibold text-text">Try one</h2>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {starters.map((t, i) => {
          const Icon = t.icon;
          return (
            <motion.button
              key={t.id}
              type="button"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 + 0.06 * i }}
              disabled={start.isPending}
              onClick={() => start.mutate(t)}
              className="group flex items-start gap-3 rounded-xl border border-border p-3 text-left hover:border-[rgb(139_151_255/0.5)] hover:bg-[rgb(99_102_241/0.06)]"
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-accent" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-text">{t.label}</span>
                <span className="block text-xs text-muted">{t.example}</span>
              </span>
              <ArrowRight className="mt-0.5 size-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
            </motion.button>
          );
        })}
      </div>
      {start.isError && <p className="mt-2 text-xs text-danger">{start.error.message}</p>}
    </section>
  );
}
