/**
 * The browser side of a NEXUS session.
 *
 * The session is an HttpOnly cookie set by /auth/login: page scripts cannot read it, so
 * an injected script cannot steal it. Requests send it with `credentials: "include"`;
 * WebSockets and download links send it by themselves. A 401 fires
 * `nexus:unauthorized`, and the app shell then sends the user to the sign-in page.
 */
const LEGACY_KEY = "nexus-token";

/** Earlier versions kept the token in localStorage: remove it wherever it is left. */
export function forgetLegacyToken(): void {
  try {
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    /* storage blocked: nothing to remove */
  }
}

export function onUnauthorized(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("nexus:unauthorized"));
}
