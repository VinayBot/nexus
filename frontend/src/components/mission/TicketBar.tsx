"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, Ticket, Wrench } from "lucide-react";
import { useRouter } from "next/navigation";
import { post } from "@/lib/api";
import type { Mission } from "@/lib/queries";
import { useActiveMission } from "@/stores/missions";

/** A new ticket: its id, where it was emailed, and a one-click hand-off to the Ticket Solver. */
export function TicketBar({ ticketId, emailedTo }: { ticketId: string; emailedTo?: string | null }) {
  const qc = useQueryClient();
  const router = useRouter();
  const setActive = useActiveMission((s) => s.setActive);
  const solve = useMutation({
    mutationFn: () =>
      post<Mission>("/missions", {
        task: `Solve ticket ${ticketId}`,
        playbook: "ticket_solver",
        inputs: { ticket_id: ticketId },
      } as never),
    onSuccess: (m) => {
      void qc.invalidateQueries({ queryKey: ["missions"] });
      setActive(m.id);
      router.push(`/missions?m=${m.id}`);
    },
  });
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border bg-[rgb(var(--accent-rgb)/0.06)] px-4 py-2.5">
      <Ticket className="size-4 text-accent" />
      <span className="text-sm text-text">
        Ticket <span className="font-mono font-semibold">{ticketId}</span> created
      </span>
      {emailedTo && (
        <span className="inline-flex items-center gap-1 text-xs text-muted">
          <Mail className="size-3.5" /> Emailed to {emailedTo}
        </span>
      )}
      <button
        type="button"
        className="btn btn-primary btn-sm ml-auto"
        disabled={solve.isPending}
        onClick={() => solve.mutate()}
      >
        <Wrench className="size-3.5" /> {solve.isPending ? "Starting…" : "Solve this ticket now"}
      </button>
      {solve.isError && <p className="w-full text-xs text-danger">{solve.error.message}</p>}
    </div>
  );
}
