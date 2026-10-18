"""Web Page Builder: a request like "build an HTML page with an AI blog" → a published page.

1. *Spec*: Sage turns the request into a page spec (kind, title, tagline, 3-5
   section headings with what each should cover).
2. *Write*: one plan step per section, written in parallel by Quill and Echo as
   schema-constrained JSON (paragraphs + key points), saved to ``content/``.
3. *Build*: Forge renders ``site/index.html`` from the sections with a fixed,
   professional template (``web_page.render_html``); the whole article is also
   the mission's answer, so the result is visible even before publishing.
4. *Check*: Aegis runs deterministic checks (title, one h1, sections, word count,
   no scripts). Thin sections are rewritten and the page rebuilt (fix loop).
5. *Publish* (after human approval): copied to ``data/sites/<mission>/`` and
   served by the API at ``/sites/<mission>/``; the verifier fetches nothing
   external, it re-checks the published file.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from nexus.core.services import services
from nexus.graph.schemas import (
    ExecutionResult,
    Finding,
    Plan,
    PlanStep,
    ProposedAction,
    ValidationResult,
    VerificationResult,
)
from nexus.llm.types import ChatMessage
from nexus.playbooks.base import Playbook
from nexus.playbooks.web_page import (
    PageSpec,
    Section,
    SectionOut,
    SectionPlan,
    check_page,
    render_html,
    thin_sections,
    to_markdown,
    word_count,
)

WRITERS = ("writer", "researcher")  # alternate Quill and Echo so sections are written in parallel
PAGE = "site/index.html"


def _default_spec(task: str) -> PageSpec:
    topic = re.sub(r"\s+", " ", task).strip()[:60] or "Artificial Intelligence"
    return PageSpec(
        kind="blog",
        title=f"A Practical Guide: {topic}",
        tagline="What it is, why it matters and how to get started.",
        sections=[
            SectionPlan(heading="Introduction", points="What the topic is and why it matters now."),
            SectionPlan(heading="How It Works", points="The core ideas explained simply."),
            SectionPlan(heading="Real-World Uses", points="Concrete examples people use today."),
            SectionPlan(heading="Getting Started", points="Practical first steps for a reader."),
        ],
    )


def _content_path(index: int) -> str:
    return f"content/{index:02d}.json"


def _load_sections(ws: Path, spec: PageSpec) -> list[Section]:
    out = []
    for i, plan in enumerate(spec.sections, 1):
        f = ws / _content_path(i)
        data = json.loads(f.read_text()) if f.is_file() else {"paragraphs": []}
        out.append(
            Section(
                heading=plan.heading,
                paragraphs=[p for p in data.get("paragraphs", []) if str(p).strip()],
                bullets=data.get("bullets", []),
            )
        )
    return out


class WebBuilder(Playbook):
    id = "web_builder"
    title = "Web Page Builder"
    description = (
        "Write content (blog post, article, landing or portfolio page) and publish it as "
        "a styled HTML page with a shareable link."
    )
    tournament_mode = None
    fixed_plan = True

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        svc = services()
        task = state.get("task", "")
        spec = await svc.llm.structured(
            [
                ChatMessage.system(
                    "You plan a single web page. Pick kind (blog, landing, portfolio, article, "
                    "other), a specific title, a one-sentence tagline, the audience, an accent "
                    "colour and 3-5 sections. Each section has a heading and one sentence on "
                    "what it covers. Write about the topic the user asked for."
                ),
                ChatMessage.user(f"Request:\n{task}"),
            ],
            PageSpec,
            purpose="plan:page",
            agent_id="sage",
            default=_default_spec(task),
        )
        spec = spec.model_copy(update={"sections": spec.sections[:5]})
        ws = svc.workspaces.ensure(state["mission_id"])
        (ws / "content").mkdir(exist_ok=True)
        (ws / "spec.json").write_text(spec.model_dump_json(indent=2))
        inputs = {**(state.get("inputs") or {}), "page_spec": spec.model_dump()}
        return {"inputs": inputs}

    def template_plan(self, state: dict[str, Any]) -> Plan:
        spec = PageSpec.model_validate((state.get("inputs") or {})["page_spec"])
        steps = [
            PlanStep(
                id=f"section-{i}",
                title=f"Write: {s.heading}",
                description=f"{i}|{s.points}",
                role=WRITERS[(i - 1) % len(WRITERS)],
                success_criteria="2-3 clear paragraphs saved.",
            )
            for i, s in enumerate(spec.sections, 1)
        ]
        steps.append(
            PlanStep(
                id="build-page",
                title="Build the HTML page",
                description="build",
                role="coder",
                depends_on=[s.id for s in steps],
                success_criteria="site/index.html rendered from every section.",
            )
        )
        return Plan(
            goal=f"Publish '{spec.title}'",
            steps=steps,
            source="template",
            rationale="one writer per section, then one page build",
        )

    async def _write_section(
        self, spec: PageSpec, index: int, agent_id: str, problem: str = ""
    ) -> Section:
        svc = services()
        plan = spec.sections[index - 1]
        others = ", ".join(s.heading for s in spec.sections if s is not plan)
        out = await svc.llm.structured(
            [
                ChatMessage.system(
                    f"You write one section of a {spec.kind} titled '{spec.title}' for "
                    f"{spec.audience}. Write 2-3 paragraphs of 3-4 informative sentences each, "
                    "plus up to 4 short key points. Plain sentences only, no HTML, no headings. "
                    "Be concrete and accurate."
                ),
                ChatMessage.user(
                    f"Section heading: {plan.heading}\nCover: {plan.points}\n"
                    f"Other sections (do not repeat them): {others}"
                    + (f"\n\nThe previous draft was rejected: {problem}" if problem else "")
                ),
            ],
            SectionOut,
            purpose="write",
            agent_id=agent_id,
            max_tokens=900,
            default=SectionOut(paragraphs=[plan.points]),
        )
        section = Section(heading=plan.heading, paragraphs=out.paragraphs, bullets=out.bullets)
        await svc.mcp.call(
            "workspace.write_file",
            {
                "path": _content_path(index),
                "content": json.dumps(section.model_dump(exclude={"heading"}), indent=2),
            },
            agent_id=agent_id,
            allowlist=None,
        )
        return section

    async def _build(self, mission_id: str, agent_id: str = "forge") -> tuple[str, list[Section]]:
        svc = services()
        ws = svc.workspaces.path_for(mission_id)
        spec = PageSpec.model_validate_json((ws / "spec.json").read_text())
        sections = _load_sections(ws, spec)
        page = render_html(spec, sections, mission_id=mission_id)
        await svc.mcp.call(
            "workspace.write_file",
            {"path": PAGE, "content": page},
            agent_id=agent_id,
            allowlist=None,
        )
        return page, sections

    async def run_step(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        step = payload["step"]
        agent_id = payload["agent_id"]
        if step["description"] == "build":
            _, sections = await self._build(payload["mission_id"], agent_id)
            summary = f"Built {PAGE}: {len(sections)} sections, {word_count(sections)} words"
        else:
            spec = PageSpec.model_validate(payload["inputs"]["page_spec"])
            index = int(step["description"].split("|", 1)[0])
            section = await self._write_section(spec, index, agent_id)
            words = len(" ".join(section.paragraphs).split())
            summary = f"Wrote '{section.heading}' ({words} words)"
        return Finding(
            step_id=step["id"],
            agent_id=agent_id,
            summary=summary,
            sources=["workspace.write_file"],
            ok=True,
            iterations=1,
        ).model_dump()

    async def synthesize(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Rebuild the page (rewriting thin sections after a failed check) → answer."""
        mission_id = state["mission_id"]
        ws = services().workspaces.path_for(mission_id)
        spec = PageSpec.model_validate_json((ws / "spec.json").read_text())
        validation = state.get("validation") or {}
        if validation and not validation.get("ok"):
            sections = _load_sections(ws, spec)
            weak = {s.heading for s in thin_sections(sections)} or {
                min(sections, key=lambda s: len(" ".join(s.paragraphs))).heading
            }
            for i, plan in enumerate(spec.sections, 1):
                if plan.heading in weak:
                    await self._write_section(
                        spec, i, "quill", problem="too short; write more detail"
                    )
        _, sections = await self._build(mission_id)
        return {"answer": to_markdown(spec, sections)}

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        ws = services().workspaces.path_for(state["mission_id"])
        spec = PageSpec.model_validate_json((ws / "spec.json").read_text())
        page_file = ws / PAGE
        if not page_file.is_file():
            return ValidationResult(ok=False, summary="site/index.html was not built")
        sections = _load_sections(ws, spec)
        problems = check_page(page_file.read_text(), sections)
        if problems:
            return ValidationResult(
                ok=False, summary="Page check failed", details="; ".join(problems)
            )
        return ValidationResult(
            ok=True,
            summary=f"Page check passed: {len(sections)} sections, {word_count(sections)} words, "
            "no scripts",
        )

    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        return ProposedAction(
            kind="publish_page",
            summary=f"Publish the page at /sites/{state['mission_id']}/",
            target=f"/sites/{state['mission_id']}/",
            files_touched=[PAGE],
            blast_radius="local",
        )

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        svc = services()
        src = svc.workspaces.path_for(state["mission_id"]) / "site"
        dest = svc.settings.data_dir / "sites" / state["mission_id"]
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return ExecutionResult(
            ok=True,
            summary=f"Published {PAGE}",
            details={"path": str(dest / "index.html"), "url": _page_url(state["mission_id"])},
        )

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        published = services().settings.data_dir / "sites" / state["mission_id"] / "index.html"
        if not published.is_file():
            return VerificationResult(ok=False, summary="published page missing")
        size = published.stat().st_size
        return VerificationResult(ok=size > 500, summary=f"page live ({size // 1024 + 1} KB)")

    def report_extras(self, state: dict[str, Any]) -> dict[str, Any]:
        details = (state.get("execution") or {}).get("details") or {}
        return {"preview_url": details.get("url"), "files": [PAGE] if details else None}


def _page_url(mission_id: str) -> str:
    return f"{services().settings.public_url.rstrip('/')}/sites/{mission_id}/"
