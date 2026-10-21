"""Role-based access control: one table decides who may call what.

Reads (GET) need ``viewer``. Changes default to ``operator``; settings, models,
users, chaos switches, agent edits, policies and deletes need ``owner``. A few
routes are public by design: health probes, the login/setup flow, signed email
approval links (the signature is the credential), the Google OAuth callback and
published pages.
"""

from __future__ import annotations

import re

PUBLIC: list[re.Pattern[str]] = [
    re.compile(p)
    for p in (
        r"^/api/v1/health(/ready)?$",
        r"^/api/v1/auth/(status|login|setup)$",
        r"^/api/v1/approvals/email/[^/]+$",
        r"^/api/v1/notify/google/callback$",
        r"^/sites/",
        r"^/metrics$",
    )
]

#: (methods, path pattern, minimum role). First match wins; later defaults apply.
RULES: list[tuple[set[str], re.Pattern[str], str]] = [
    (m, re.compile(p), role)
    for m, p, role in (
        ({"PUT", "POST", "DELETE"}, r"^/api/v1/(settings|models|policies)(/.*)?$", "owner"),
        ({"PUT", "POST", "DELETE"}, r"^/api/v1/notify(?!/intent$)(/.*)?$", "owner"),
        ({"PUT", "POST", "DELETE"}, r"^/api/v1/(chaos|incidents)(/.*)?$", "owner"),
        ({"PUT", "POST", "DELETE"}, r"^/api/v1/(agents|playbooks)(/.*)?$", "owner"),
        ({"PUT", "POST", "DELETE"}, r"^/api/v1/governor(/.*)?$", "owner"),
        ({"GET", "PUT", "POST", "DELETE"}, r"^/api/v1/auth/users(/.*)?$", "owner"),
        ({"DELETE"}, r"^/api/v1/missions/[^/]+$", "owner"),
        ({"POST"}, r"^/api/v1/notify/intent$", "viewer"),  # a read-only preview
        ({"POST"}, r"^/api/v1/guide(/.*)?$", "viewer"),  # asking Nova changes nothing
        ({"POST"}, r"^/api/v1/auth/logout$", "viewer"),  # anyone may end their own session
    )
]


def required_role(method: str, path: str) -> str | None:
    """Minimum role for a request, or None when the route is public."""
    if method == "OPTIONS" or any(p.search(path) for p in PUBLIC):
        return None
    for methods, pattern, role in RULES:
        if method in methods and pattern.search(path):
            return role
    return "viewer" if method in {"GET", "HEAD"} else "operator"
