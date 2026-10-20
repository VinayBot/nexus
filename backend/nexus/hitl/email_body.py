"""The result email's HTML: a summary box first, then the full output.

Layout: Summary (mission type, outcome, key result, "in short") → You asked → links →
Output → How the team did it. Plain inline styles, because mail clients ignore
stylesheets.
"""

from __future__ import annotations

import html
import re
from typing import Any

from nexus.core.config import Settings

OUTCOME = {
    "success": ("Completed", "#16a34a"),
    "partial": ("Partly done", "#d97706"),
    "rejected": ("Rejected by you", "#6b7280"),
    "blocked": ("Blocked by policy", "#dc2626"),
    "rolled_back": ("Rolled back", "#d97706"),
    "failed": ("Stopped with an error", "#dc2626"),
}


def _inline(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return re.sub(r"(?<![\w*])_([^_]+)_(?![\w*])", r"<i>\1</i>", out)


def markdown_html(md: str) -> str:
    """Just enough Markdown for an email: headings, bullets, code blocks, paragraphs."""
    parts: list[str] = []
    in_list = in_code = False
    code: list[str] = []
    for line in md.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                parts.append(
                    '<pre style="background:#f4f4f5;padding:10px;border-radius:6px;'
                    'font-size:12px;overflow:auto">' + html.escape("\n".join(code)) + "</pre>"
                )
                code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)", line)
        if in_list and not bullet:
            parts.append("</ul>")
            in_list = False
        if bullet:
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline(bullet.group(1))}</li>")
        elif m := re.match(r"^(#{1,3})\s+(.*)", line):
            size = {1: 20, 2: 16, 3: 15}[len(m.group(1))]
            parts.append(f'<p style="font-size:{size}px;font-weight:600">{_inline(m.group(2))}</p>')
        elif line.strip():
            parts.append(f"<p>{_inline(line)}</p>")
    if in_list:
        parts.append("</ul>")
    return "\n".join(parts)


TYPE_NAMES = {
    "web_builder": "Web page",
    "council_qa": "Question",
    "self_healing": "Fix service",
    "project_builder": "Build API",
    "ticket_creator": "New ticket",
    "ticket_solver": "Solve ticket",
    "dynamic": "Custom team",
}


def in_short(answer: str, sentences: int = 2) -> str:
    """The first sentences of the answer's first real paragraph (no headings, lists, code)."""
    for block in re.split(r"\n\s*\n", answer):
        line = block.strip()
        if (
            not line
            or line[0] in "#-*`>_|"
            or line[:2].rstrip(".").isdigit()
            or line.startswith("**")
        ):
            continue
        text = re.sub(r"[`*_]", "", " ".join(line.split()))
        parts = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(parts[:sentences])[:420]
    return ""


def explain_failure(error: str) -> str:
    if re.search(r"LLMUnavailable|gave no answer|timeout", error, re.I):
        return "The local model did not answer in time (the Mac may have been short of memory or asleep). Retry from NEXUS."
    if re.search(r"token", error, re.I) and re.search(r"cap|limit", error, re.I):
        return "The mission hit its token budget before finishing. Retry, or ask for something smaller."
    return "Something went wrong inside the agent graph. Retrying usually works; details are below."


def key_result(row: Any, report: dict[str, Any], api: str) -> str:
    if row.status == "failed":
        return "Not finished"
    if report.get("preview_url"):
        url = html.escape(report["preview_url"])
        return f'Page published: <a href="{url}">{url}</a>'
    if report.get("ticket_id"):
        return f"Ticket <b>{html.escape(report['ticket_id'])}</b> filed in the tracker"
    if report.get("download"):
        n = len(report.get("files") or [])
        return (
            f'Project ready: <a href="{api}{html.escape(report["download"])}">download the zip</a>'
            + (f" ({n} files)" if n else "")
        )
    verified = next((h for h in report.get("highlights") or [] if h.startswith("Verified:")), "")
    if row.playbook in {"self_healing", "ticket_solver"} and verified:
        return html.escape(verified)
    return "Answer below"


def compose_result(row: Any, settings: Settings) -> tuple[str, str, str]:
    report: dict[str, Any] = row.report or {}
    key = "failed" if row.status == "failed" else (row.outcome or "partial")
    label, colour = OUTCOME.get(key, (key, "#6b7280"))
    ui = settings.ui_url.rstrip("/")
    api = settings.public_url.rstrip("/")
    answer = str(report.get("answer") or "")
    short = explain_failure(row.error or "") if row.status == "failed" else in_short(answer)
    took = report.get("duration_s")
    facts = [
        ("Mission", TYPE_NAMES.get(row.playbook or "", "Auto")),
        ("Outcome", label + (f" in {round(float(took))} s" if took else "")),
        ("Result", key_result(row, report, api)),
    ]
    rows = "".join(
        f'<tr><td style="color:#71717a;padding:2px 12px 2px 0;font-size:13px">{k}</td>'
        f'<td style="font-size:13px">{v if k == "Result" else html.escape(v)}</td></tr>'
        for k, v in facts
    )
    summary = f"""<div style="background:#fafafa;border:1px solid #e4e4e7;border-left:4px solid {colour};border-radius:8px;padding:14px 16px;margin-bottom:18px">
<p style="margin:0 0 8px;font-size:12px;font-weight:600;color:{colour};text-transform:uppercase;letter-spacing:.04em">Summary</p>
<table style="border-collapse:collapse">{rows}</table>
{f'<p style="margin:10px 0 0;font-size:14px;color:#27272a"><b>In short:</b> {html.escape(short)}</p>' if short else ""}
</div>"""
    links = [f'<a href="{ui}/missions?m={row.id}">Open the mission in NEXUS</a>']
    if row.status == "failed":
        output = f'<pre style="white-space:pre-wrap;font-size:12px;color:#52525b">{html.escape(row.error or "Unknown error")[:1500]}</pre>'
    else:
        output = markdown_html(answer or str(report.get("summary") or ""))
    steps = "".join(f"<li>{_inline(h)}</li>" for h in dict.fromkeys(report.get("highlights") or []))
    body = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;color:#18181b">
{summary}
<p style="color:#71717a;font-size:12px;margin:0">You asked</p>
<p style="font-size:15px;margin:4px 0 12px">&ldquo;{html.escape(row.task)}&rdquo;</p>
<p style="font-size:13px">{" &middot; ".join(links)}</p>
<hr style="border:none;border-top:1px solid #e4e4e7">
<p style="color:#71717a;font-size:12px">{"Error" if row.status == "failed" else "Output"}</p>
{output}
{f'<hr style="border:none;border-top:1px solid #e4e4e7"><p style="color:#71717a;font-size:12px">How the team did it</p><ol style="font-size:13px;color:#3f3f46">{steps}</ol>' if steps else ""}
<p style="color:#a1a1aa;font-size:11px">Sent by NEXUS &middot; {int(report.get("tokens") or row.tokens or 0):,} tokens</p>
</div>"""
    text = (
        f"SUMMARY\nMission: {facts[0][1]}\nOutcome: {facts[1][1]}\n"
        f"Result: {re.sub(r'<[^>]+>', '', facts[2][1])}\n"
        + (f"In short: {short}\n" if short else "")
        + f"\nYou asked: {row.task}\n\n{answer or row.error or ''}"
    )
    return f"[NEXUS] {label}: {row.title[:90]}", body, text
