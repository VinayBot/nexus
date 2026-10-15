"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useAnimationControls } from "motion/react";
import Link from "next/link";
import { Robot, RobotDefs } from "@/components/robots/Robot";
import { PageHeader } from "@/components/ui/PageHeader";
import { FALLBACK_AVATARS } from "@/lib/agents";
import { get, post, put } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initialRobot } from "@/lib/robotMachine";
import { useLive } from "@/stores/live";

interface Switch {
  id: string;
  title: string;
  symptom: string;
  file: string;
  enabled: boolean;
}
interface Chaos {
  switches: Switch[];
  health: { status: string; error_rate: number; latency_ms: number | null };
  metrics: { orders_processed?: number; errors?: number };
  history: { ts: number; status: string; error_rate: number }[];
  auto_heal: boolean;
}
interface Incident {
  id: string;
  ts: number;
  signal: string;
  detail: string;
  status: string;
  mission_id: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  healthy: "var(--success)",
  degraded: "var(--warning)",
  down: "var(--error)",
};

/** ECG-style heartbeat: a beat per sample, amplitude grows with the error rate. */
function Heartbeat({ points }: { points: { status: string; errorRate: number }[] }) {
  const W = 600;
  const H = 90;
  const pts = points.slice(-60);
  const step = W / Math.max(1, 60);
  let d = `M0,${H / 2}`;
  pts.forEach((p, i) => {
    const x = i * step;
    const amp = 10 + p.errorRate * 60;
    d += ` L${x + step * 0.3},${H / 2} L${x + step * 0.42},${H / 2 - amp} L${x + step * 0.55},${H / 2 + amp * 0.6} L${x + step * 0.68},${H / 2} L${x + step},${H / 2}`;
  });
  const last = pts[pts.length - 1];
  const color = STATUS_COLOR[last?.status ?? "healthy"] ?? "var(--success)";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-24 w-full" preserveAspectRatio="none" aria-label="Service heartbeat">
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
    </svg>
  );
}

function Bell({ sw, onRing, busy }: { sw: Switch; onRing: () => void; busy: boolean }) {
  const controls = useAnimationControls();
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        void controls.start({ rotate: [0, 22, -18, 14, -10, 6, 0], transition: { duration: 1.4 } });
        onRing();
      }}
      className={cn(
        "panel group flex flex-col items-center gap-2 p-4 text-center transition-colors hover:bg-surface-hover",
        sw.enabled && "border-danger",
      )}
      aria-pressed={sw.enabled}
      aria-label={`${sw.enabled ? "Silence" : "Ring"} the ${sw.title} bell`}
    >
      <motion.svg animate={controls} viewBox="0 0 60 70" className="w-14" style={{ transformOrigin: "30px 6px" }}>
        <path d="M30,4 v6" stroke="#6b4a24" strokeWidth={3} />
        <path
          d="M14,46 C14,22 20,12 30,12 C40,12 46,22 46,46 L50,52 L10,52 Z"
          fill={sw.enabled ? "#c8341f" : "#b07a1c"}
          stroke="#3b2a1a"
          strokeWidth={1.5}
        />
        <path d="M18,36 h24" stroke="rgba(255,255,255,0.3)" />
        <circle cx={30} cy={56} r={4.5} fill="#3b2a1a" />
        {sw.enabled && (
          <circle cx={30} cy={30} r={22} fill="none" stroke="#ff4d4f" opacity={0.4} className="animate-alarm" />
        )}
      </motion.svg>
      <span className="font-display text-sm text-text">{sw.title}</span>
      <span className="text-[11px] leading-snug text-muted">{sw.symptom}</span>
      <span className="font-mono text-[10px] text-faint">{sw.file}</span>
      <span className={cn("chip", sw.enabled ? "border-danger text-danger" : "")}>
        {sw.enabled ? "ringing — bug injected" : "silent"}
      </span>
    </button>
  );
}

export default function Page() {
  const qc = useQueryClient();
  const chaos = useQuery({ queryKey: ["chaos"], queryFn: () => get<Chaos>("/chaos"), refetchInterval: 5000 });
  const incidents = useQuery({
    queryKey: ["incidents"],
    queryFn: () => get<Incident[]>("/incidents"),
    refetchInterval: 8000,
  });
  const liveHealth = useLive((s) => s.healthHistory);
  const health = useLive((s) => s.health) ?? chaos.data?.health;
  const refresh = () => void qc.invalidateQueries({ queryKey: ["chaos"] });
  const toggle = useMutation({
    mutationFn: (s: Switch) => post(`/chaos/${s.id}`, { enabled: !s.enabled }),
    onSuccess: refresh,
  });
  const reset = useMutation({ mutationFn: () => post("/chaos/reset"), onSuccess: refresh });
  const autoHeal = useMutation({
    mutationFn: (enabled: boolean) => put("/chaos/auto-heal", { enabled }),
    onSuccess: refresh,
  });
  const heal = useMutation({ mutationFn: (id: string) => post<{ mission_id: string }>(`/incidents/${id}/heal`) });
  const points = liveHealth.length
    ? liveHealth
    : (chaos.data?.history ?? []).map((h) => ({ status: h.status, errorRate: h.error_rate }));
  const status = health?.status ?? "unknown";
  const kuro = initialRobot(0);

  return (
    <>
      <RobotDefs />
      <PageHeader
        title="Chaos Shrine"
        kanji="神社"
        description="Ring a bell to inject a real bug into the live demo-service (it reloads within seconds). Kuro the Watcher notices, opens an incident and — with auto-heal on — the Self-Healing playbook begins."
        actions={
          <>
            <label className="chip cursor-pointer gap-2">
              <input
                type="checkbox"
                checked={chaos.data?.auto_heal ?? false}
                onChange={(e) => autoHeal.mutate(e.target.checked)}
              />
              Auto-heal
            </label>
            <button type="button" onClick={() => reset.mutate()} className="chip cursor-pointer hover:text-text">
              Restore baseline
            </button>
          </>
        }
      />
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="panel p-4">
          <div className="flex items-center gap-3">
            <span
              className="size-3 rounded-full"
              style={{
                background: STATUS_COLOR[status] ?? "var(--text-faint)",
                boxShadow: `0 0 12px ${STATUS_COLOR[status] ?? "transparent"}`,
              }}
            />
            <h2 className="font-display text-lg capitalize">demo-service: {status}</h2>
            <span className="ml-auto font-mono text-xs text-muted">
              error rate {((health?.error_rate ?? 0) * 100).toFixed(0)}% · {health?.latency_ms ?? "—"} ms ·{" "}
              {chaos.data?.metrics.orders_processed ?? 0} orders · {chaos.data?.metrics.errors ?? 0} errors
            </span>
          </div>
          <Heartbeat points={points} />
        </section>
        <section className="panel flex items-center gap-3 p-3">
          <Robot
            avatar={FALLBACK_AVATARS.kuro!}
            state={{
              ...kuro,
              mode: status === "healthy" ? "idle" : "alarm",
              expression: status === "healthy" ? "normal" : "error",
            }}
            size={72}
            showBubble={false}
          />
          <p className="text-xs leading-snug text-muted">
            <span className="font-display text-sm text-text">Kuro</span> watches from the roof, polling health every 2
            s. Two unhealthy readings in a row open an incident.
          </p>
        </section>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" data-tour="bells">
        {chaos.data?.switches.map((s) => (
          <Bell key={s.id} sw={s} busy={toggle.isPending} onRing={() => toggle.mutate(s)} />
        ))}
      </div>

      <section className="panel mt-3 p-3">
        <h2 className="panel-title mb-2 text-sm text-gold">Incidents</h2>
        {!incidents.data?.length && <p className="text-xs text-faint">No incidents yet. Ring a bell.</p>}
        <ul className="divide-y divide-border/40">
          {incidents.data?.map((i) => (
            <li key={i.id} className="flex flex-wrap items-start gap-3 py-2">
              <span className={cn("chip", i.status === "open" ? "border-danger text-danger" : "text-success")}>
                {i.status}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">
                  <span className="font-mono text-gold">{i.id}</span> · {i.signal}
                </p>
                <details>
                  <summary className="cursor-pointer text-[11px] text-faint">error digest</summary>
                  <pre className="mt-1 max-h-40 overflow-auto rounded bg-black/40 p-2 font-mono text-[10.5px] text-muted">
                    {i.detail}
                  </pre>
                </details>
              </div>
              <span className="text-[11px] text-faint">{new Date(i.ts * 1000).toLocaleTimeString()}</span>
              {i.mission_id && (
                <Link href={`/dojo?m=${i.mission_id}`} className="chip hover:text-text">
                  Mission →
                </Link>
              )}
              {i.status === "open" && (
                <button type="button" onClick={() => heal.mutate(i.id)} className="chip cursor-pointer hover:text-text">
                  Heal again
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
