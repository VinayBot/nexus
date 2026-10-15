"use client";

import Link from "next/link";
import { StatusDot } from "@/components/dojo/MissionList";
import { useMissions } from "@/lib/queries";
import { EmptyState } from "./EmptyState";
import { PageHeader } from "./PageHeader";

/** Landing for per-mission screens when no mission is in the URL. */
export function MissionPicker({
  title,
  kanji,
  target,
  hint,
}: {
  title: string;
  kanji: string;
  target: string;
  hint: string;
}) {
  const { data, isLoading } = useMissions(30);
  return (
    <>
      <PageHeader title={title} kanji={kanji} description={hint} />
      {isLoading ? (
        <EmptyState title="Loading missions…" />
      ) : !data?.length ? (
        <EmptyState
          title="No missions yet"
          action={
            <Link className="chip" href="/dojo">
              Go to Mission Control
            </Link>
          }
        >
          Begin a mission or ring a bell in the Chaos Shrine first.
        </EmptyState>
      ) : (
        <ul className="panel divide-y divide-border/40">
          {data.map((m) => (
            <li key={m.id}>
              <Link href={`${target}/${m.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-hover">
                <StatusDot status={m.status} />
                <span className="flex-1 truncate text-sm">{m.title}</span>
                <span className="text-xs text-faint">
                  {m.playbook} · {m.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
