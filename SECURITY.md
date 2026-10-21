# Security policy

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's **Report a vulnerability** (private
advisory) on this repository. Expect a first answer within 7 days.

## Supported versions

Only the latest release on `main` receives fixes.

## How NEXUS protects itself

| Area | Measure |
|---|---|
| Accounts | Argon2id hashes; JWT sessions (12 h) in an HttpOnly, SameSite=Lax cookie (Bearer for API clients, never in URLs) with server-side revocation; login limit of 5 per minute per user and address |
| CSRF / CORS | unsafe requests and WebSocket handshakes that carry the cookie must come from a listed origin; CORS lists exact origins, methods and headers |
| Authorization | one policy table for every route (viewer, operator, owner); approvals record the signed-in user |
| Abuse limits | per user: missions per minute and a daily token quota, stored in the database |
| Agents | per-agent MCP tool allowlists, workspace path jail, sandboxed tests with no network, prompt-injection detection, secret and PII redaction, fenced untrusted text |
| HTTP | CSP, `nosniff`, frame-deny, referrer policy; published pages may not run scripts |
| Email | only when a prompt asks; Google sign-in with the `gmail.send` scope only; approval links are signed, single-use, and need a POST to confirm |
| Secrets | `.env` and `backend/data/` are ignored by git and Docker; a weak `NEXUS_SECRET_KEY` is replaced by a random key (file mode 0600) |
| Supply chain | pip-audit, pnpm audit and CodeQL in CI; Dependabot updates |

Accepted risk: the chromadb advisories PYSEC-2026-311, -3813, -3814 and -3815 concern
Chroma's HTTP server. NEXUS embeds Chroma as a library (`PersistentClient`) and runs no
Chroma server, so they are ignored in `pip-audit` with this justification.
