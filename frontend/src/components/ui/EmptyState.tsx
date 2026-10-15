import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Calm placeholder used for empty, not-yet-available and error states. */
export function EmptyState({
  title,
  children,
  tone = "neutral",
  action,
  className,
}: {
  title: string;
  children?: ReactNode;
  tone?: "neutral" | "error";
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("panel grid place-items-center px-6 py-12 text-center", className)}
      role={tone === "error" ? "alert" : undefined}
    >
      <div className="max-w-md">
        <div
          className={cn(
            "mx-auto mb-4 size-3 rounded-full animate-lantern",
            tone === "error" ? "bg-danger shadow-[0_0_14px_var(--error)]" : "bg-gold shadow-[var(--glow-gold)]",
          )}
        />
        <h2 className="font-display text-lg text-text">{title}</h2>
        {children && <div className="mt-2 text-sm text-muted">{children}</div>}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}
