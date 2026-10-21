/**
 * The browser side of a NEXUS session: the JWT from /auth/login, kept in localStorage.
 *
 * Requests send it as `Authorization: Bearer …`. Links and WebSockets cannot send
 * headers, so `withToken` adds `?token=` for them (the backend accepts either).
 * A 401 clears the session and fires `nexus:unauthorized`; the app shell then
 * sends the user to the sign-in page.
 */
const KEY = "nexus-token";

export function getToken(): string | null {
  try {
    return typeof window === "undefined" ? null : localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    /* private mode: the session lasts until reload */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function withToken(url: string): string {
  const token = getToken();
  if (!token) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
}

export function onUnauthorized(): void {
  clearToken();
  if (typeof window !== "undefined") window.dispatchEvent(new Event("nexus:unauthorized"));
}
