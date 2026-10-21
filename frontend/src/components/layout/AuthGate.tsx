"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ApiError, get } from "@/lib/api";
import { forgetLegacyToken } from "@/lib/auth";
import { useMe } from "@/lib/me";

/**
 * Keeps the app behind sign-in: no session (or an expired one) → /login, and back
 * to the same page afterwards. When auth is switched off on the server it lets
 * everything through.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: () => get<{ auth_enabled: boolean; setup_required: boolean }>("/auth/status"),
    staleTime: 60_000,
    retry: 1,
  });
  useEffect(forgetLegacyToken, []);
  const enabled = status.data?.auth_enabled;
  const me = useMe(); // the session cookie is HttpOnly: the server says who we are
  const signedOut = me.error instanceof ApiError && me.error.status === 401;
  const toLogin = () => router.replace(`/login?next=${encodeURIComponent(pathname)}`);

  useEffect(() => {
    if (enabled && signedOut) toLogin();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, signedOut]);
  useEffect(() => {
    window.addEventListener("nexus:unauthorized", toLogin);
    return () => window.removeEventListener("nexus:unauthorized", toLogin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const ready = status.data && (!enabled || me.data);
  if (status.isError) return <>{children}</>; // backend down: the pages show their own errors
  if (!ready) {
    return (
      <div className="grid h-dvh place-items-center" role="status" aria-label="Checking your session">
        <Loader2 className="size-6 animate-spin text-accent" />
      </div>
    );
  }
  return <>{children}</>;
}
