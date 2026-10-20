"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Mail } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { post } from "@/lib/api";

interface Intent {
  requested: boolean;
  to: string[];
  needs_address: boolean;
  delivery: "google" | "smtp" | "mailpit";
}

/** Live preview under the task box: "The result will be emailed to …" (only when asked). */
export function EmailIntentHint({ task }: { task: string }) {
  const [debounced, setDebounced] = useState(task);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(task), 350);
    return () => clearTimeout(t);
  }, [task]);
  const asks = /\b(send|e-?mail|mail|share|forward)\b/i.test(debounced);
  const intent = useQuery({
    queryKey: ["intent", debounced],
    queryFn: () => post<Intent>("/notify/intent", { task: debounced }),
    enabled: asks && debounced.trim().length > 5,
    staleTime: 30_000,
  });
  const d = asks ? intent.data : undefined;
  return (
    <AnimatePresence>
      {d?.requested && (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="flex items-start gap-1.5 overflow-hidden text-xs"
          data-testid="email-hint"
        >
          <Mail className="mt-0.5 size-3.5 shrink-0 text-accent" />
          {d.needs_address ? (
            <span className="text-warning">
              You asked for email, but no address is set.{" "}
              <Link href="/settings" className="underline">
                Add yours in Settings
              </Link>
            </span>
          ) : (
            <span className="text-muted">
              The result will be emailed to <span className="text-text">{d.to.join(", ")}</span>
              {d.delivery === "mailpit" && (
                <>
                  {" "}
                  (after you{" "}
                  <Link href="/settings" className="underline">
                    sign in with Google
                  </Link>
                  )
                </>
              )}
            </span>
          )}
        </motion.p>
      )}
    </AnimatePresence>
  );
}
