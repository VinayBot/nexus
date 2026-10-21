const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * Backend base URL (override with NEXT_PUBLIC_API_URL).
 *
 * The session is an HttpOnly, SameSite=Lax cookie, so the API must be on the same *site*
 * as the page. `localhost` and `127.0.0.1` are different sites to a browser: when both
 * sides are loopback, the API host follows the page's host (the port stays as configured).
 */
export function apiBase(configured: string | undefined, pageHost: string | null): string {
  const url = new URL(configured ?? "http://127.0.0.1:8000");
  if (pageHost && LOOPBACK.has(url.hostname) && LOOPBACK.has(pageHost)) url.hostname = pageHost;
  return url.toString().replace(/\/$/, "");
}

export const API_URL = apiBase(
  process.env.NEXT_PUBLIC_API_URL,
  typeof window === "undefined" ? null : window.location.hostname,
);

/** WebSocket base derived from the API URL (http→ws, https→wss). */
export const WS_URL = API_URL.replace(/^http/, "ws");
