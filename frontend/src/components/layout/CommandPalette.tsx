"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useHikari } from "@/components/guide/Hikari";
import { post } from "@/lib/api";
import { ALL_NAV_ITEMS } from "@/lib/nav";
import { useMissions } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";
import { useTour } from "@/stores/tour";
import { useUi } from "@/stores/ui";

const BELLS = [
  ["null_handling", "Null-handling bug"],
  ["off_by_one", "Off-by-one bug"],
  ["bad_config", "Bad config value"],
  ["slow_dependency", "Slow dependency"],
  ["schema_mismatch", "Schema mismatch"],
] as const;

/** ⌘K: navigate, start missions, ring chaos bells, jump to checkpoints, ask Hikari. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const missions = useMissions(10);
  const active = useActiveMission((s) => s.activeId);
  const setActive = useActiveMission((s) => s.setActive);
  const tour = useTour();
  const ui = useUi();
  const ask = useHikari((s) => s.ask);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (fn: () => void) => () => {
    setOpen(false);
    setQuery("");
    fn();
  };
  const item =
    "flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm aria-selected:bg-surface-hover aria-selected:text-text";

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-start bg-black/50 pt-[14vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <Command
        label="Command palette"
        className="panel mx-auto w-[min(620px,92vw)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command.Input
          autoFocus
          value={query}
          onValueChange={setQuery}
          placeholder="Type a command or ask Hikari…"
          className="w-full border-b border-border/60 bg-transparent px-4 py-3 text-sm outline-none"
        />
        <Command.List className="max-h-[55vh] overflow-y-auto p-2 text-muted">
          <Command.Empty>
            <button type="button" className={item} onClick={go(() => ask(query))}>
              Ask Hikari: “{query}”
            </button>
          </Command.Empty>
          <Command.Group
            heading="Go to"
            className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-faint [&_[cmdk-group-heading]]:uppercase"
          >
            {ALL_NAV_ITEMS.map((n) => (
              <Command.Item
                key={n.href}
                className={item}
                onSelect={go(() => router.push(n.needsMission && active ? `${n.href}/${active}` : n.href))}
              >
                <n.icon className="size-4" /> {n.label}
              </Command.Item>
            ))}
          </Command.Group>
          <Command.Group
            heading="Missions"
            className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-faint [&_[cmdk-group-heading]]:uppercase"
          >
            <Command.Item
              className={item}
              onSelect={go(async () => {
                const m = await post<{ id: string }>("/missions", {
                  task: "What is the difference between ReAct and Plan-and-Execute agents?",
                  playbook: "council_qa",
                });
                setActive(m.id);
                router.push(`/dojo?m=${m.id}`);
              })}
            >
              ▶ Start a demo Council Q&A mission
            </Command.Item>
            {missions.data?.slice(0, 6).map((m) => (
              <Command.Item
                key={m.id}
                className={item}
                value={`open ${m.title}`}
                onSelect={go(() => {
                  setActive(m.id);
                  router.push(`/dojo?m=${m.id}`);
                })}
              >
                Open: {m.title.slice(0, 60)} <span className="ml-auto text-[10px] text-faint">{m.status}</span>
              </Command.Item>
            ))}
            {active && (
              <Command.Item className={item} onSelect={go(() => router.push(`/timetravel/${active}`))}>
                ⟲ Jump to checkpoints of the active mission
              </Command.Item>
            )}
          </Command.Group>
          <Command.Group
            heading="Chaos"
            className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-faint [&_[cmdk-group-heading]]:uppercase"
          >
            {BELLS.map(([id, label]) => (
              <Command.Item
                key={id}
                className={item}
                onSelect={go(() => void post(`/chaos/${id}`, { enabled: true }).then(() => router.push("/shrine")))}
              >
                🔔 Ring the {label} bell
              </Command.Item>
            ))}
            <Command.Item className={item} onSelect={go(() => void post("/chaos/reset"))}>
              Restore demo-service baseline
            </Command.Item>
          </Command.Group>
          <Command.Group
            heading="Dojo"
            className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-faint [&_[cmdk-group-heading]]:uppercase"
          >
            <Command.Item className={item} onSelect={go(() => tour.start())}>
              Guided tour
            </Command.Item>
            <Command.Item className={item} onSelect={go(() => tour.start(undefined, true))}>
              Presentation mode (auto-advancing tour)
            </Command.Item>
            <Command.Item className={item} onSelect={go(ui.toggleTheme)}>
              Toggle sunset / night theme
            </Command.Item>
            <Command.Item className={item} onSelect={go(ui.togglePerformance)}>
              Toggle performance mode
            </Command.Item>
            <Command.Item className={item} onSelect={go(ui.toggleSound)}>
              Toggle sound
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}
