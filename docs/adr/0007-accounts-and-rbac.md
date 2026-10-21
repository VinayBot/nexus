# ADR 0007: Accounts and role-based access control

**Status:** accepted (2026-10-21)

## Context

NEXUS started as a single-user localhost tool. Human-in-the-loop only means something if
we know *which* human approved: an approval is a security decision, and anyone who can reach
the API could otherwise approve, change policies or delete missions. The reviews of earlier
assignments also flagged missing authentication and RBAC.

## Decision

- **Accounts** in the `users` table, passwords hashed with **Argon2id** (`argon2-cffi`),
  which is memory-hard and upgrades its own parameters on login (`needs_rehash`).
- **Sessions** are short-lived **JWTs** (HS256, 12 h by default) signed with
  `NEXUS_SECRET_KEY`; a weak or placeholder key is replaced by a random 48-byte key stored
  in `data/secret.key` (0600). Browsers hold the session in an **HttpOnly, SameSite=Lax
  cookie** (`nexus_session`; `Secure` over HTTPS), so page scripts never see it. API
  clients send the same token as `Authorization: Bearer`. Tokens are never accepted in
  URLs, where they would leak into logs and history.
- **CSRF and cross-site WebSockets:** an unsafe request or WebSocket handshake carrying the
  cookie must come from a listed origin (or the API's own); browsers always send `Origin`
  cross-site. CORS lists exact methods and headers, with credentials.
- **Three roles**: viewer (read), operator (run missions, decide approvals, time travel),
  owner (settings, models, users, chaos, agents, deletes).
- **One policy table** (`auth/policy.py`) maps method + path to the minimum role, applied
  as a router dependency to every API route. New routes are protected by default (reads
  need viewer, writes need operator); exceptions are listed explicitly.
- The account is **re-read from the database on every request**, so a role change or a
  deleted account takes effect immediately, not at token expiry.
- Approvals store the **signed-in username** (`by`), ignoring any name sent by the client.
- **Public by design:** health probes, setup/login, signed single-use email-approval links
  (the signature is the credential), the Google OAuth callback and published pages.
- **Login rate limit:** 5 attempts per minute per username and client address.

## Consequences

- The first visit asks for an owner account; `NEXUS_BOOTSTRAP_USERS` seeds accounts for
  CI, e2e and containers. `NEXUS_AUTH_ENABLED=false` exists only for tests and throwaway demos.
- WebSockets and download links authenticate with the cookie, which the browser sends by
  itself. The frontend therefore talks to the API on the page's own site (for local use,
  `localhost` and `127.0.0.1` are aligned automatically).
- Rate limits and revoked sessions live in the database (ADR 0009), so they hold across
  restarts and replicas.
- Amended 2026-10-21: the token moved from `localStorage` (readable by any injected script)
  to the HttpOnly cookie, and `?token=` was removed.
