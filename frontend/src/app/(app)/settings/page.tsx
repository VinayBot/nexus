"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ModelPicker } from "@/components/settings/ModelPicker";
import { PageHeader } from "@/components/ui/PageHeader";
import { get, put } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useUi } from "@/stores/ui";

interface SettingsView {
  model_profile: string;
  models: { main: string; fast: string; embed: string };
  fallback_model: string | null;
  num_ctx: number;
  llm_max_concurrency: number;
  llm_timeout_s: number;
  pruning_strategy: "sliding_window" | "summarise";
  verify_window_s: number;
  auto_heal: boolean;
  mission_token_limit: number;
  sandbox_backend: string;
  smtp: string;
  owner_email: string;
  public_url: string;
  ollama_base_url: string;
  default_secret: boolean;
}
interface Policy {
  id: string;
  description: string;
  kind: string;
  applies_to: string[];
  value: unknown;
  enabled: boolean;
}

function Row({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-3 border-b border-border/30 py-2 text-sm">
      <div>
        <p>{label}</p>
        {hint && <p className="text-[10.5px] text-faint">{hint}</p>}
      </div>
      <div>{children}</div>
    </div>
  );
}

export default function Page() {
  const qc = useQueryClient();
  const s = useQuery({ queryKey: ["settings"], queryFn: () => get<SettingsView>("/settings") });
  const policies = useQuery({ queryKey: ["policies"], queryFn: () => get<Policy[]>("/policies") });
  const save = useMutation({
    mutationFn: (patch: Partial<SettingsView>) => put<SettingsView>("/settings", patch as never),
    onSuccess: (d) => qc.setQueryData(["settings"], d),
  });
  const savePolicies = useMutation({
    mutationFn: (p: Policy[]) => put<Policy[]>("/policies", p as never),
    onSuccess: (d) => qc.setQueryData(["policies"], d),
  });
  const ui = useUi();
  const [draft, setDraft] = useState<Policy[] | null>(null);
  const pol = draft ?? policies.data ?? [];
  const d = s.data;

  return (
    <>
      <PageHeader title="Settings" description="Every setting here changes the running backend immediately." />
      <div className="grid gap-3 xl:grid-cols-2">
        <ModelPicker />
        <section className="panel p-4">
          <h2 className="panel-title text-sm ">Live knobs</h2>
          {d && (
            <>
              <Row label="LLM concurrency" hint="Resource Governor slots (lowered automatically under memory pressure)">
                <input
                  type="range"
                  min={1}
                  max={4}
                  value={d.llm_max_concurrency}
                  onChange={(e) => save.mutate({ llm_max_concurrency: Number(e.target.value) })}
                  aria-label="LLM concurrency"
                />
                <span className="ml-2 font-mono">{d.llm_max_concurrency}</span>
              </Row>
              <Row label="Pruning strategy">
                {(["sliding_window", "summarise"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => save.mutate({ pruning_strategy: v })}
                    className={cn("chip mr-1 cursor-pointer", d.pruning_strategy === v && "border-accent text-accent")}
                  >
                    {v}
                  </button>
                ))}
              </Row>
              <Row label="Verify window" hint="Seconds of live traffic watched after a fix">
                <input
                  type="number"
                  min={2}
                  max={120}
                  value={d.verify_window_s}
                  onChange={(e) => save.mutate({ verify_window_s: Number(e.target.value) })}
                  className="w-20 rounded border border-border bg-black/40 px-2 py-1"
                  aria-label="Verify window seconds"
                />
              </Row>
              <Row label="Auto-heal incidents">
                <input
                  type="checkbox"
                  checked={d.auto_heal}
                  onChange={(e) => save.mutate({ auto_heal: e.target.checked })}
                  aria-label="Auto-heal"
                />
              </Row>
              <Row label="Token cap / mission">{d.mission_token_limit.toLocaleString()} (policy)</Row>
              <Row label="Sandbox">{d.sandbox_backend}</Row>
              <Row label="Email">
                {d.smtp} → {d.owner_email}
              </Row>
              {d.default_secret && (
                <p className="mt-2 rounded bg-warning/10 px-2 py-1 text-xs text-warning">
                  NEXUS_SECRET_KEY is the dev default — set your own in .env before sharing approval links.
                </p>
              )}
            </>
          )}
        </section>
        <section className="panel p-4">
          <h2 className="panel-title text-sm ">Appearance</h2>
          <Row label="Theme">
            {(["sunset", "night"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => ui.setTheme(t)}
                className={cn("chip mr-1 cursor-pointer capitalize", ui.theme === t && "border-accent text-accent")}
              >
                {t}
              </button>
            ))}
          </Row>
          <Row label="Performance mode" hint="No particles, paused ambient animation">
            <input
              type="checkbox"
              checked={ui.performanceMode}
              onChange={ui.togglePerformance}
              aria-label="Performance mode"
            />
          </Row>
          <Row label="Sound" hint="Soft UI sounds (muted by default)">
            <input type="checkbox" checked={ui.soundOn} onChange={ui.toggleSound} aria-label="Sound" />
          </Row>
        </section>
        <section className="panel p-4">
          <div className="flex items-center">
            <h2 className="panel-title text-sm ">Safety policies</h2>
            {draft && (
              <button
                type="button"
                onClick={() => savePolicies.mutate(draft, { onSuccess: () => setDraft(null) })}
                className="chip ml-auto cursor-pointer text-success"
              >
                Save policies
              </button>
            )}
          </div>
          <ul className="mt-2 space-y-1">
            {pol.map((p, i) => (
              <li key={p.id} className="flex items-start gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={p.enabled}
                  onChange={(e) => setDraft(pol.map((x, j) => (j === i ? { ...x, enabled: e.target.checked } : x)))}
                  aria-label={p.id}
                  className="mt-0.5"
                />
                <div>
                  <p className="font-mono ">{p.id}</p>
                  <p className="text-muted">
                    {p.description}
                    {p.value != null ? ` (${String(p.value)})` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          {savePolicies.error && <p className="text-xs text-danger">{savePolicies.error.message}</p>}
        </section>
      </div>
    </>
  );
}
