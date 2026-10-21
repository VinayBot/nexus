"use client";

import { Lock } from "lucide-react";
import { ROLE_LABEL, useCan, type Role } from "@/lib/me";

/**
 * Disables every control inside when the signed-in role is below `min`, with a short
 * note saying who can change it. The server enforces the same rule (auth/policy.py).
 */
export function RoleGate({ min, children }: { min: Role; children: React.ReactNode }) {
  const allowed = useCan(min);
  return (
    <>
      {!allowed && (
        <p className="col-span-full flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-2 text-xs text-muted">
          <Lock className="size-3.5" /> Read-only for your role. Changes here need the {ROLE_LABEL[min]} role.
        </p>
      )}
      <fieldset disabled={!allowed} className="contents">
        {children}
      </fieldset>
    </>
  );
}
