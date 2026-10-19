"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, Cpu, Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Profile {
  id: string;
  label: string;
  description: string;
  ram_gb: number;
  models: { main: string; fast: string; code: string | null; embed: string; fallback: string | null };
  missing: string[];
}
interface Install {
  profile: string;
  state: "downloading" | "done" | "failed";
  model: string;
  completed: number;
  total: number;
  error: string | null;
}
interface ModelsInfo {
  active: string;
  models: Profile["models"];
  installed: string[];
  profiles: Profile[];
  install: Install | null;
}

const gb = (b: number) => (b / 1e9).toFixed(1);

/**
 * Pick the model profile. Installed profiles switch at once; a missing one offers
 * "Install and switch": the backend downloads it (progress below) and switches when done.
 */
export function ModelPicker() {
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState<string | null>(null);
  const info = useQuery({
    queryKey: ["models"],
    queryFn: () => get<ModelsInfo>("/models"),
    refetchInterval: (q) => (q.state.data?.install?.state === "downloading" ? 1500 : false),
  });
  const done = (d: ModelsInfo) => {
    qc.setQueryData(["models"], d);
    void qc.invalidateQueries({ queryKey: ["settings"] });
    void qc.invalidateQueries({ queryKey: ["system-info"] });
    setConfirming(null);
  };
  const choose = useMutation({
    mutationFn: (profile: string) => put<ModelsInfo>("/models", { profile }),
    onSuccess: done,
  });
  const install = useMutation({
    mutationFn: (profile: string) => post<ModelsInfo>("/models/install", { profile }),
    onSuccess: done,
  });
  const d = info.data;
  const job = d?.install;
  const busy = job?.state === "downloading";
  const error = choose.error ?? install.error;

  return (
    <section className="panel p-4 xl:col-span-2" aria-label="Models">
      <div className="flex flex-wrap items-center gap-2">
        <Cpu className="size-4 text-accent" />
        <h2 className="panel-title text-sm">Models</h2>
        <span className="text-xs text-faint">
          Local, through Ollama. Switching unloads the old models to free memory.
        </span>
      </div>
      {info.isError && <p className="mt-2 text-xs text-danger">Could not load models: {info.error.message}</p>}
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {d?.profiles.map((p) => {
          const active = p.id === d.active;
          const ready = p.missing.length === 0;
          const mine = job?.profile === p.id;
          return (
            <motion.div
              key={p.id}
              whileHover={{ y: active ? 0 : -2 }}
              className={cn(
                "relative flex flex-col rounded-xl border p-4",
                active ? "border-[var(--accent-strong)] bg-[rgb(var(--accent-rgb)/0.1)]" : "border-border",
              )}
              data-testid={`profile-${p.id}`}
            >
              <div className="flex items-center gap-2">
                <span className="font-semibold text-text">{p.label}</span>
                <span className="text-xs text-faint">~{p.ram_gb} GB RAM</span>
                {active && (
                  <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-[var(--accent-strong)] px-2 py-0.5 text-[11px] font-semibold text-white">
                    <Check className="size-3" /> Active
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs leading-snug text-muted">{p.description}</p>
              <dl className="mt-2 grid grid-cols-[52px_1fr] gap-x-2 gap-y-0.5 font-mono text-[11px]">
                <dt className="text-faint">main</dt>
                <dd className="truncate text-text">{p.models.main}</dd>
                <dt className="text-faint">fast</dt>
                <dd className="truncate text-text">{p.models.fast}</dd>
                <dt className="text-faint">code</dt>
                <dd className="truncate text-text">{p.models.code ?? p.models.main}</dd>
              </dl>

              {mine && busy && (
                <div className="mt-3" role="status" aria-label="Download progress">
                  <p className="flex items-center gap-1.5 text-xs text-muted">
                    <Loader2 className="size-3.5 animate-spin" /> Downloading {job.model}
                    {job.total > 0 && ` · ${gb(job.completed)} / ${gb(job.total)} GB`}
                  </p>
                  <div className="mt-1.5 h-1.5 rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-[var(--accent-strong)] transition-[width] duration-700"
                      style={{ width: `${job.total ? (job.completed / job.total) * 100 : 3}%` }}
                    />
                  </div>
                </div>
              )}
              {mine && job.state === "failed" && (
                <p className="mt-2 text-xs text-danger">Download failed: {job.error}</p>
              )}

              {!active && !(mine && busy) && (
                <div className="mt-auto pt-3">
                  {confirming === p.id ? (
                    <div className="rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-xs text-text">
                      <p>
                        Download {p.missing.join(", ")} (several GB) and switch to it? On a 16 GB Mac with a browser and
                        an IDE open, {p.label} can be slow or run out of memory. You can switch back at any time.
                      </p>
                      <div className="mt-2 flex gap-2">
                        <button type="button" className="btn btn-primary btn-sm" onClick={() => install.mutate(p.id)}>
                          <Download className="size-3.5" /> Download and switch
                        </button>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      disabled={busy || choose.isPending}
                      onClick={() => (ready ? choose.mutate(p.id) : setConfirming(p.id))}
                      className="btn btn-ghost btn-sm w-full"
                    >
                      {ready ? (
                        `Switch to ${p.label}`
                      ) : (
                        <>
                          <Download className="size-3.5" /> Install and switch
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error.message}</p>}
    </section>
  );
}
