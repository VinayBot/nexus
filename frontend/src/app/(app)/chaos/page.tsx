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
  const step = W / 60;
  // newest samples sit at the right edge; before the first sample the trace is a flat line
  const offset = (60 - pts.length) * step;
  let d = `M0,${H / 2} L${offset},${H / 2}`;
  pts.forEach((p, i) => {
    const x = offset + i * step;
    const amp = 10 + p.errorRate * 60;
    d += ` L${x + step * 0.3},${H / 2} L${x + step * 0.42},${H / 2 - amp} L${x + step * 0.55},${H / 2 + amp * 0.6} L${x + step * 0.68},${H / 2} L${x + step},${H / 2}`;
  });
  const last = pts[pts.length - 1];
  const color = STATUS_COLOR[last?.status ?? "healthy"] ?? "var(--success)";
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="holo-grid mt-2 h-24 w-full rounded-md"
      preserveAspectRatio="none"
      aria-label="Service heartbeat"
    >
      <rect className="ecg-sweep" x={0} y={0} width={40} height={H} fill="url(#ecg-fade)" />
      <defs>
        <linearGradient id="ecg-fade" x1="0" x2="1">
          <stop offset="0" stopColor={color} stopOpacity={0} />
          <stop offset="1" stopColor={color} stopOpacity={0.18} />
        </linearGradient>
      </defs>
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

/** A chaos switch: a hazard module with a lever. Armed = red core, rotating hazard ring, shake. */
function ChaosSwitch({ sw, onToggle, busy }: { sw: Switch; onToggle: () => void; busy: boolean }) {
  const controls = useAnimationControls();
  const on = sw.enabled;
  const core = on ? "#ff4d4f" : "#3fd18b";
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        void controls.start({ x: [0, -4, 4, -3, 3, 0], transition: { duration: 0.45 } });
        onToggle();
      }}
      className={cn(
        "panel card-lift group flex flex-col items-center gap-2 p-4 text-center hover:bg-surface-hover",
        on && "border-danger shadow-[0_0_24px_-6px_var(--error)]",
      )}
      aria-pressed={on}
      aria-label={`${on ? "Disarm" : "Arm"} the ${sw.title} switch`}
    >
      <motion.svg animate={controls} viewBox="0 0 60 60" className="w-14 overflow-visible">
        <path
          d="M30,2 L54,16 L54,44 L30,58 L6,44 L6,16 Z"
          fill="#141016"
          stroke={core}
          strokeOpacity={0.6}
          strokeWidth={1.5}
        />
        <motion.circle
          cx={30}
          cy={30}
          r={19}
          fill="none"
          stroke={on ? "#ffb020" : "rgba(255,255,255,0.15)"}
          strokeWidth={3}
          strokeDasharray="5 4"
          animate={{ rotate: on ? 360 : 0 }}
          transition={{ repeat: on ? Infinity : 0, duration: 3, ease: "linear" }}
          style={{ transformOrigin: "30px 30px" }}
        />
        <circle cx={30} cy={30} r={11} fill={core} opacity={0.25} className={on ? "animate-alarm" : undefined} />
        <circle cx={30} cy={30} r={6} fill={core} style={{ filter: `drop-shadow(0 0 6px ${core})` }} />
        <motion.rect
          x={28}
          y={8}
          width={4}
          height={16}
          rx={2}
          fill="#d6dbe3"
          animate={{ rotate: on ? 40 : -40 }}
          transition={{ type: "spring", stiffness: 300, damping: 14 }}
          style={{ transformOrigin: "30px 24px" }}
        />
      </motion.svg>
      <span className="font-display text-sm text-text">{sw.title}</span>
      <span className="text-[11px] leading-snug text-muted">{sw.symptom}</span>
      <span className="font-mono text-[10px] text-faint">{sw.file}</span>
      <span className={cn("chip", on ? "border-danger text-danger" : "")}>{on ? "armed — bug injected" : "safe"}</span>
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
  const hawk = initialRobot(0);

  return (
    <>
      <RobotDefs />
      <PageHeader
        title="Chaos Lab"
        description="Arm a switch to inject a real bug into the live demo-service (it reloads within seconds). Hawk the Watcher notices, opens an incident and — with auto-heal on — the Self-Healing playbook begins."
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
            <button type="button" onClick={() => reset.mutate()} className="btn btn-ghost btn-sm">
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
            avatar={FALLBACK_AVATARS.hawk!}
            state={{
              ...hawk,
              mode: status === "healthy" ? "idle" : "alarm",
              expression: status === "healthy" ? "normal" : "error",
            }}
            size={72}
            showBubble={false}
          />
          <p className="text-xs leading-snug text-muted">
            <span className="font-display text-sm text-text">Hawk</span> watches from the catwalk, polling health every
            2 s. Two unhealthy readings in a row open an incident.
          </p>
        </section>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" data-tour="chaos-switches">
        {chaos.data?.switches.map((s) => (
          <ChaosSwitch key={s.id} sw={s} busy={toggle.isPending} onToggle={() => toggle.mutate(s)} />
        ))}
      </div>

      <section className="panel mt-3 p-3">
        <h2 className="panel-title mb-2 text-sm text-gold">Incidents</h2>
        {!incidents.data?.length && <p className="text-xs text-faint">No incidents yet. Arm a switch.</p>}
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
                <Link href={`/missions?m=${i.mission_id}`} className="chip hover:text-text">
                  Mission →
                </Link>
              )}
              {i.status === "open" && (
                <button type="button" onClick={() => heal.mutate(i.id)} className="btn btn-primary btn-sm">
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
