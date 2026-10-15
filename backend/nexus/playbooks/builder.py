"""Project Builder (scoped): requirements + docs → a small, tested service.

Honest scope: small services only (≤ 8 files: a FastAPI CRUD API or a CLI tool),
because 3–8B local models cannot reliably build more. Steps:

1. *Context*: uploaded docs are indexed in the knowledge base; the Scribe extracts a
   spec (kind, entity, fields, constraints, file list).
2. *Resources*: the matching template from ``playbooks/templates`` is gathered.
3. *Build*: one plan step per file; files without dependencies are written in
   parallel by Tetsu (code) and Mamoru (tests), each adapting the template.
4. *Test*: the Guardian's tests run in the sandbox; failures are repaired file by
   file until green or the fix limit is reached.
5. *Deliver* (after approval): a zip of the project, downloadable from the report.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from nexus.core.event_types import MemoryRecalled
from nexus.core.events import emit
from nexus.core.services import services
from nexus.graph.schemas import (
    EvidenceItem,
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
from nexus.safety.guardrails import fence

TEMPLATES = Path(__file__).parent / "templates"
MAX_FILES = 8


class FileSpec(BaseModel):
    path: str = Field(pattern=r"^(app|tests)/[\w/]+\.py$")
    purpose: str
    depends_on: list[str] = Field(default_factory=list)


class ProjectSpec(BaseModel):
    kind: Literal["fastapi_crud", "cli_tool"]
    name: str = Field(description="Short project name")
    entity: str = Field(description="Main resource or concept, singular, e.g. Book")
    fields: list[str] = Field(default_factory=list, description="e.g. ['title: str', 'year: int']")
    constraints: list[str] = Field(default_factory=list)
    files: list[FileSpec] = Field(min_length=2, max_length=MAX_FILES)


class FileOut(BaseModel):
    content: str = Field(description="The complete file content.")


class Repair(BaseModel):
    path: str
    content: str = Field(description="The complete corrected file content.")


def _template(kind: str) -> dict[str, str]:
    root = TEMPLATES / kind
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*.py"))
        if p.name != "__init__.py"
    }


def _slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:40]


class ProjectBuilder(Playbook):
    id = "project_builder"
    title = "Project Builder (scoped)"
    description = "Build a small FastAPI CRUD API or CLI tool (≤ 8 files) from requirements and docs, with tests."
    tournament_mode = None
    fixed_plan = True

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        svc = services()
        inputs = dict(state.get("inputs") or {})
        docs = inputs.get("docs") or []
        memory = svc.extras.get("memory")
        for d in docs:
            if memory is not None:
                await memory.add(
                    "docs",
                    d["text"][:6000],
                    {"title": f"upload: {d['name']}", "mission_id": state["mission_id"]},
                )
        doc_text = "\n\n".join(fence(d["text"][:3000], source=d["name"]) for d in docs)
        spec = await svc.llm.structured(
            [
                ChatMessage.system(
                    "You turn requirements into a small project spec. kind is fastapi_crud for "
                    f"web APIs and cli_tool for command-line tools. List at most {MAX_FILES} files "
                    "under app/ and tests/ (always include app/__init__-free modules and at least "
                    "one tests/test_*.py). Use depends_on for files that import others."
                ),
                ChatMessage.user(
                    f"Requirements:\n{state['task']}\n\nDocuments:\n{doc_text or '(none)'}"
                ),
            ],
            ProjectSpec,
            purpose="plan:spec",
            role="main",
            agent_id="kanji",
            default=ProjectSpec(
                kind="fastapi_crud",
                name="items-api",
                entity="Item",
                fields=["name: str", "price: float"],
                files=[
                    FileSpec(path=p, purpose="from template") for p in _template("fastapi_crud")
                ],
            ),
        )
        template = _template(spec.kind)
        emit(
            "memory.recalled",
            MemoryRecalled(
                collection="templates",
                query=spec.kind,
                hits=[
                    {"id": p, "collection": "templates", "title": p, "score": 1.0} for p in template
                ],
            ),
            agent_id="kagemi",
        )
        ws = svc.workspaces.ensure(state["mission_id"])
        for pkg in ("app", "tests"):
            (ws / pkg).mkdir(exist_ok=True)
            (ws / pkg / "__init__.py").write_text("")
        inputs.update(spec=spec.model_dump(), templates=template)
        evidence = EvidenceItem(
            kind="note",
            title=f"Spec: {spec.name} ({spec.kind})",
            content=f"Entity {spec.entity}: {', '.join(spec.fields)}\nConstraints: {'; '.join(spec.constraints) or '-'}\nFiles: "
            + ", ".join(f.path for f in spec.files),
        ).with_hash()
        return {"inputs": inputs, "evidence": [evidence.model_dump()]}

    def template_plan(self, state: dict[str, Any]) -> Plan:
        spec = ProjectSpec.model_validate((state.get("inputs") or {})["spec"])
        paths = {f.path for f in spec.files}
        steps = [
            PlanStep(
                id=_slug(f.path),
                title=f"Write {f.path}",
                description=f"{f.path}: {f.purpose}",
                role="tester" if f.path.startswith("tests/") else "coder",
                depends_on=[_slug(d) for d in f.depends_on if d in paths and d != f.path],
                success_criteria="File written and importable.",
            )
            for f in spec.files
        ]
        return Plan(
            goal=f"Build {spec.name}",
            steps=steps,
            source="template",
            rationale="file-level plan from the spec",
        )

    async def run_step(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        svc = services()
        inputs = payload.get("inputs") or {}
        spec = ProjectSpec.model_validate(inputs["spec"])
        path = payload["step"]["description"].split(":", 1)[0]
        ws = svc.workspaces.path_for(payload["mission_id"])
        written = {
            str(p.relative_to(ws)): p.read_text()
            for p in sorted(ws.rglob("*.py"))
            if p.name != "__init__.py" and str(p.relative_to(ws)) != path
        }
        template = (inputs.get("templates") or {}).get(path) or next(
            (
                c
                for p, c in (inputs.get("templates") or {}).items()
                if Path(p).name == Path(path).name
            ),
            "",
        )
        out = await svc.llm.structured(
            [
                ChatMessage.system(services().registry.get(payload["agent_id"]).system_prompt),
                ChatMessage.user(
                    f"Project: {spec.name} ({spec.kind}). Entity {spec.entity} with fields {', '.join(spec.fields)}.\n"
                    f"Constraints: {'; '.join(spec.constraints) or 'none'}.\nAll files: "
                    + ", ".join(f"{f.path} ({f.purpose})" for f in spec.files)
                    + f"\n\nWrite the complete content of {path}. Import project modules as `from app.x import y`."
                    + (f"\n\nAdapt this template:\n```python\n{template}\n```" if template else "")
                    + "".join(
                        f"\n\nAlready written {p}:\n```python\n{c[:2000]}\n```"
                        for p, c in list(written.items())[:4]
                    )
                ),
            ],
            FileOut,
            purpose="code",
            max_tokens=2000,
            agent_id=payload["agent_id"],
            default=FileOut(content=template or f'"""{path} (generation failed)"""\n'),
        )
        content = out.content.strip().removeprefix("```python").removesuffix("```").strip() + "\n"
        res = await svc.mcp.call(
            "workspace.write_file",
            {"path": path, "content": content},
            agent_id=payload["agent_id"],
            allowlist=None,
        )
        return Finding(
            step_id=payload["step"]["id"],
            agent_id=payload["agent_id"],
            summary=f"Wrote {path} ({len(content.splitlines())} lines)"
            if res.ok
            else f"Could not write {path}: {res.text}",
            sources=["workspace.write_file"],
            ok=res.ok,
            iterations=1,
        ).model_dump()

    async def synthesize(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """First pass: summarise. After a failed validation: repair the implicated file."""
        svc = services()
        ws = svc.workspaces.path_for(state["mission_id"])
        validation = state.get("validation") or {}
        if validation and not validation.get("ok"):
            output = str((validation.get("tests") or {}).get("output", ""))[-3000:]
            files = {
                str(p.relative_to(ws)): p.read_text()
                for p in sorted(ws.rglob("*.py"))
                if p.name != "__init__.py" and "__pycache__" not in p.parts
            }
            implicated = re.findall(r"\b((?:app|tests)/[\w/]+\.py)", output)
            fallback = next(
                (p for p in reversed(implicated) if p in files), next(iter(files), "app/main.py")
            )
            shown = "\n\n".join(f"File {p}:\n```python\n{c}\n```" for p, c in files.items())
            fix = await svc.llm.structured(
                [
                    ChatMessage.system(svc.registry.get("tetsu").system_prompt),
                    ChatMessage.user(
                        f"The project's tests fail:\n{output}\n\n{shown}\n\nFind the file that "
                        "causes the failure (often not the test file) and return its corrected "
                        "full content."
                    ),
                ],
                Repair,
                purpose="code",
                max_tokens=2000,
                agent_id="tetsu",
                default=Repair(path=fallback, content=files.get(fallback, "")),
            )
            path = fix.path if fix.path in files else fallback
            await svc.mcp.call(
                "workspace.write_file",
                {"path": path, "content": fix.content},
                agent_id="tetsu",
                allowlist=None,
            )
            return {"answer": f"Repaired {path} after failing tests."}
        built = sorted(str(p.relative_to(ws)) for p in ws.rglob("*.py"))
        return {"answer": "Built files:\n" + "\n".join(f"- {f}" for f in built)}

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        ws = services().workspaces.path_for(state["mission_id"])
        run = await services().sandbox.run_tests(ws, "tests", timeout_s=120)
        tests = run.as_dict()
        if run.ok and run.passed > 0:
            return ValidationResult(
                ok=True, summary=f"Project tests pass: {tests['summary']}", tests=tests
            )
        return ValidationResult(
            ok=False,
            summary=f"Project tests fail: {tests['summary']}",
            details="\n".join(run.failures[:5]),
            tests=tests,
        )

    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        ws = services().workspaces.path_for(state["mission_id"])
        files = sorted(str(p.relative_to(ws)) for p in ws.rglob("*.py"))
        return ProposedAction(
            kind="write_project",
            summary=f"Package {len(files)} files as a downloadable zip",
            files_touched=files,
            blast_radius="local",
        )

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        ws = services().workspaces.path_for(state["mission_id"])
        out_dir = services().settings.data_dir / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{state['mission_id']}.zip"
        files = [
            p
            for p in sorted(ws.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith(".")
        ]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, p.relative_to(ws))
        return ExecutionResult(
            ok=True,
            summary=f"Packaged {len(files)} files",
            details={"zip": str(target), "files": [str(p.relative_to(ws)) for p in files]},
        )

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        zip_path = Path(((state.get("execution") or {}).get("details") or {}).get("zip", ""))
        if not zip_path.is_file():
            return VerificationResult(ok=False, summary="zip missing")
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
        return VerificationResult(ok=bool(names), summary=f"zip contains {len(names)} files")

    def report_extras(self, state: dict[str, Any]) -> dict[str, Any]:
        details = (state.get("execution") or {}).get("details") or {}
        return {
            "files": details.get("files"),
            "download": f"/api/v1/missions/{state['mission_id']}/download"
            if details.get("zip")
            else None,
            "scope": "small services only (≤ 8 files)",
        }
