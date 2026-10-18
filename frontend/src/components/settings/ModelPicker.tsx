"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, Cpu } from "lucide-react";
import { get, put } from "@/lib/api";
import { cn } from "@/lib/cn";

interface Profile {
  id: string;
  label: string;
  description: string;
  ram_gb: number;
  models: { main: string; fast: string; code: string | null; embed: string; fallback: string | null };
  missing: string[];
}
interface ModelsInfo {
  active: string;
  models: Profile["models"];
  installed: string[];
  profiles: Profile[];
}

/** Pick the model profile; takes effect for the next LLM call and survives restarts. */
export function ModelPicker() {
  const qc = useQueryClient();
  const info = useQuery({ queryKey: ["models"], queryFn: () => get<ModelsInfo>("/models") });
  const choose = useMutation({
    mutationFn: (profile: string) => put<ModelsInfo>("/models", { profile }),
    onSuccess: (d) => {
      qc.setQueryData(["models"], d);
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["system-info"] });
    },
  });
  const d = info.data;
  return (
    <section className="panel p-4 xl:col-span-2" aria-label="Models">
      <div className="flex items-center gap-2">
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
          return (
            <motion.button
              key={p.id}
              type="button"
              whileHover={{ y: ready ? -2 : 0 }}
              disabled={!ready || active || choose.isPending}
              onClick={() => choose.mutate(p.id)}
              aria-pressed={active}
              className={cn(
                "relative rounded-xl border p-4 text-left transition-colors disabled:cursor-default",
                active ? "border-[var(--indigo)] bg-[rgb(99_102_241/0.1)]" : "border-border hover:border-white/20",
                !ready && "opacity-70",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="font-semibold text-text">{p.label}</span>
                <span className="text-xs text-faint">~{p.ram_gb} GB RAM</span>
                {active && (
                  <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-[var(--indigo)] px-2 py-0.5 text-[11px] font-semibold text-white">
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
              {!ready && (
                <p className="mt-2 rounded-md bg-black/30 px-2 py-1 font-mono text-[10.5px] text-warning">
                  ollama pull {p.missing.join(" ")}
                </p>
              )}
            </motion.button>
          );
        })}
      </div>
      {choose.isError && <p className="mt-2 text-xs text-danger">{choose.error.message}</p>}
    </section>
  );
}
