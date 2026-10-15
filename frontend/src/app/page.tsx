import Link from "next/link";
import { SkyBackdrop } from "@/components/scenery/SkyBackdrop";

export default function Gate() {
  return (
    <main className="relative grid min-h-dvh place-items-center px-6 text-center">
      <SkyBackdrop />
      <div>
        <h1 className="font-display text-7xl font-extrabold tracking-[0.3em] text-[var(--sun-core)] drop-shadow-[0_0_30px_rgba(247,164,64,0.6)]">
          NEXUS
        </h1>
        <p className="mt-4 text-lg text-muted">A dynamic multi-agent dojo running entirely on local models.</p>
        <Link
          href="/dojo"
          className="mt-8 inline-block rounded-full border border-border-strong bg-surface px-8 py-3 font-display text-lg text-text shadow-[var(--glow-gold)] hover:bg-surface-hover"
        >
          Enter the Dojo
        </Link>
      </div>
    </main>
  );
}
