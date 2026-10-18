"""Rendering and checking for the Web Page Builder.

The agents write the *words* (a spec and one JSON file per section); this module
turns them into a single self-contained ``index.html``. Layout and CSS come from
a fixed, professional template because a 3B model writing raw HTML/CSS is
unreliable, while it writes good prose. Agent text is HTML-escaped and only a
tiny inline Markdown subset (**bold**, *italic*, `code`) is allowed, so the
published page can never contain agent-written markup or scripts.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Literal

from pydantic import BaseModel, Field

Accent = Literal["indigo", "emerald", "amber", "rose", "sky"]
ACCENTS: dict[str, tuple[str, str]] = {
    "indigo": ("#4f46e5", "#eef2ff"),
    "emerald": ("#059669", "#ecfdf5"),
    "amber": ("#d97706", "#fffbeb"),
    "rose": ("#e11d48", "#fff1f2"),
    "sky": ("#0284c7", "#f0f9ff"),
}
MIN_WORDS = 250


class SectionPlan(BaseModel):
    heading: str = Field(description="Section heading, 2-8 words.")
    points: str = Field(description="What this section should cover, one sentence.")


class PageSpec(BaseModel):
    kind: Literal["blog", "landing", "portfolio", "article", "other"] = "blog"
    title: str = Field(description="Page title, 3-10 words.")
    tagline: str = Field(description="One-sentence subtitle shown under the title.")
    audience: str = Field(default="general readers")
    accent: Accent = "indigo"
    sections: list[SectionPlan] = Field(min_length=2, max_length=6)


class SectionOut(BaseModel):
    paragraphs: list[str] = Field(
        min_length=1, max_length=4, description="2-3 paragraphs of 2-4 sentences each."
    )
    bullets: list[str] = Field(
        default_factory=list, max_length=6, description="Optional key points (may be empty)."
    )


class Section(BaseModel):
    heading: str
    paragraphs: list[str]
    bullets: list[str] = Field(default_factory=list)


def _inline(text: str) -> str:
    """Escape, then allow **bold**, *italic* and `code` only."""
    out = html.escape(text.strip())
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "section"


def word_count(sections: list[Section]) -> int:
    return sum(len(" ".join([*s.paragraphs, *s.bullets]).split()) for s in sections)


def to_markdown(spec: PageSpec, sections: list[Section]) -> str:
    parts = [f"# {spec.title}", f"_{spec.tagline}_"]
    for s in sections:
        parts.append(f"## {s.heading}")
        parts.extend(s.paragraphs)
        if s.bullets:
            parts.append("\n".join(f"- {b}" for b in s.bullets))
    return "\n\n".join(parts)


CSS = """
:root{--accent:ACCENT;--accent-soft:SOFT;--ink:#0f172a;--muted:#475569;--line:#e2e8f0}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font:17px/1.7 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:#fff}
header.hero{background:linear-gradient(135deg,var(--accent-soft),#fff 70%);border-bottom:1px solid var(--line)}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
nav.top{display:flex;justify-content:space-between;align-items:center;padding:18px 0;font-size:14px;color:var(--muted)}
nav.top b{color:var(--accent);letter-spacing:.02em}
.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.15;margin:40px 0 12px;letter-spacing:-.02em}
.hero p.tag{font-size:19px;color:var(--muted);margin:0 0 18px}
.meta{font-size:14px;color:var(--muted);padding-bottom:40px}
.meta span{display:inline-block;background:var(--accent-soft);color:var(--accent);border-radius:999px;padding:2px 10px;margin-right:8px;font-weight:600}
aside.toc{margin:32px 0;padding:16px 20px;border:1px solid var(--line);border-radius:12px;background:#f8fafc}
aside.toc strong{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
aside.toc ol{margin:8px 0 0;padding-left:20px}aside.toc a{color:var(--ink);text-decoration:none}
aside.toc a:hover{color:var(--accent)}
section{margin:44px 0}section h2{font-size:26px;letter-spacing:-.01em;margin:0 0 12px;scroll-margin-top:20px}
section h2::before{content:"";display:block;width:36px;height:3px;background:var(--accent);border-radius:2px;margin-bottom:12px}
ul.points{background:var(--accent-soft);border-radius:12px;padding:14px 18px 14px 36px}
ul.points li{margin:4px 0}
code{background:#f1f5f9;border-radius:4px;padding:1px 5px;font-size:.9em}
footer{border-top:1px solid var(--line);margin-top:64px;padding:28px 0 48px;font-size:14px;color:var(--muted)}
@media (max-width:600px){body{font-size:16px}.hero h1{margin-top:24px}}
"""


def render_html(spec: PageSpec, sections: list[Section], *, mission_id: str) -> str:
    accent, soft = ACCENTS.get(spec.accent, ACCENTS["indigo"])
    minutes = max(1, round(word_count(sections) / 220))
    toc = "".join(
        f'<li><a href="#{slug(s.heading)}">{html.escape(s.heading)}</a></li>' for s in sections
    )
    body = []
    for s in sections:
        paras = "".join(f"<p>{_inline(p)}</p>" for p in s.paragraphs if p.strip())
        bullets = (
            '<ul class="points">' + "".join(f"<li>{_inline(b)}</li>" for b in s.bullets) + "</ul>"
            if s.bullets
            else ""
        )
        body.append(
            f'<section id="{slug(s.heading)}"><h2>{html.escape(s.heading)}</h2>{paras}{bullets}</section>'
        )
    title = html.escape(spec.title)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{html.escape(spec.tagline)}">
<meta name="generator" content="NEXUS Web Page Builder (mission {mission_id})">
<title>{title}</title><style>{CSS.replace("ACCENT", accent).replace("SOFT", soft)}</style></head>
<body><header class="hero"><div class="wrap">
<nav class="top"><b>{html.escape(spec.kind.title())}</b><span>Written by the NEXUS agent team</span></nav>
<h1>{title}</h1><p class="tag">{html.escape(spec.tagline)}</p>
<div class="meta"><span>{minutes} min read</span>For {html.escape(spec.audience)}</div>
</div></header>
<main class="wrap"><aside class="toc"><strong>In this {html.escape(spec.kind)}</strong><ol>{toc}</ol></aside>
{"".join(body)}</main>
<footer><div class="wrap">Generated locally by NEXUS: planned by Sage, written by Quill and Echo,
built by Forge, checked by Aegis and approved by a human.</div></footer>
</body></html>
"""


class _Probe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: dict[str, int] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] = self.tags.get(tag, 0) + 1
        self._in_title = tag == "title"

    def handle_endtag(self, tag: str) -> None:
        self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def check_page(page: str, sections: list[Section]) -> list[str]:
    """Deterministic quality checks; returns the problems found (empty = pass)."""
    probe = _Probe()
    probe.feed(page)
    problems: list[str] = []
    if not probe.title.strip():
        problems.append("page has no <title>")
    if probe.tags.get("h1", 0) != 1:
        problems.append("page needs exactly one <h1>")
    if probe.tags.get("script"):
        problems.append("page contains a <script> tag")
    if probe.tags.get("section", 0) < 2:
        problems.append("page has fewer than 2 sections")
    words = word_count(sections)
    if words < MIN_WORDS:
        problems.append(f"only {words} words of content (need {MIN_WORDS}+)")
    for s in thin_sections(sections):
        problems.append(f"section '{s.heading}' is too thin")
    return problems


def thin_sections(sections: list[Section]) -> list[Section]:
    return [s for s in sections if len(" ".join(s.paragraphs).split()) < 40]
