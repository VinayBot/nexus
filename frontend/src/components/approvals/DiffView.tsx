import { cn } from "@/lib/cn";

/** Unified diff / evidence text with +/- line colouring. */
export function DiffView({ text, className }: { text: string; className?: string }) {
  return (
    <pre
      className={cn(
        "max-h-60 overflow-auto rounded-lg bg-[#0b0d12] p-2.5 font-mono text-[11px] leading-relaxed",
        className,
      )}
    >
      {text.split("\n").map((line, i) => {
        const add = line.startsWith("+") && !line.startsWith("+++");
        const del = line.startsWith("-") && !line.startsWith("---");
        return (
          <div
            key={i}
            className={cn(
              add && "bg-success/10 text-success",
              del && "bg-danger/10 text-[#ff8f8f]",
              line.startsWith("@@") && "text-accent/80",
              !add && !del && "text-muted",
            )}
          >
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}
