"""Self-Healing preparation: everything that should be deterministic, not guessed.

* copy the live (buggy) code into the mission workspace;
* reproduce: run the existing tests in the sandbox, and ask Mamoru for a focused
  reproduction test — kept only if it really FAILS on the buggy code;
* locate suspect files from traceback frames and from identifiers in the error
  text that are defined in the code;
* look up the Fix Library for a similar past incident and check whether its patch
  still applies and passes the tests (memory makes repeat incidents fast).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from nexus.core.services import services
from nexus.llm.types import ChatMessage
from nexus.playbooks.patching import apply_search_replace
from nexus.safety.guardrails import fence

FRAME = re.compile(r'File "[^"]*?/(app/[\w/]+\.py)", line (\d+)')
PYTEST_FRAME = re.compile(r"\b(app/[\w/]+\.py):(\d+)")
MENTION = re.compile(r"\b(app/[\w/]+\.py)\b")
WORD = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{3,})\b")
MAX_CANDIDATES = 3


class ReproTest(BaseModel):
    reasoning: str = Field(description="What behaviour the test checks.")
    test_code: str = Field(description="A complete pytest module importing from the app package.")


def focus_line(root: Path, digest: str) -> dict[str, Any] | None:
    """Deepest application frame in the traceback: where the exception is raised."""
    frames = FRAME.findall(digest)
    for file, line in reversed(frames):
        path = root / file
        if path.exists():
            lines = path.read_text().splitlines()
            n = int(line)
            if 1 <= n <= len(lines):
                return {"file": file, "line": n, "code": lines[n - 1].strip()}
    return None


def candidate_files(root: Path, *texts: str) -> list[str]:
    """Suspect files: traceback frames first, then files defining identifiers in the text."""
    found: list[str] = []
    blob = "\n".join(texts)
    for pattern in (FRAME, PYTEST_FRAME):
        for m in reversed(pattern.findall(blob)):
            if m[0] not in found and (root / m[0]).exists():
                found.append(m[0])
    for path in MENTION.findall(blob):
        if path not in found and (root / path).exists():
            found.append(path)
    words = {w for w in WORD.findall(blob) if not w.islower() or "_" in w or len(w) > 6}
    for path in sorted(root.glob("app/*.py")):
        rel = str(path.relative_to(root))
        if rel in found:
            continue
        text = path.read_text(errors="ignore")
        if any(
            re.search(rf"^\s*(def {re.escape(w)}\(|{re.escape(w)}\s*=)", text, re.M) for w in words
        ):
            found.append(rel)
    # the pipeline is a symptom site, not usually the cause: try it last
    found.sort(key=lambda f: f.endswith("pipeline.py"))
    return found[:MAX_CANDIDATES] or ["app/orders.py"]


async def reproduce(
    mission_id: str, incident_id: str, digest: str, files: dict[str, str]
) -> dict[str, Any]:
    """Run existing tests, then try an LLM-written reproduction test."""
    hub = services().mcp
    existing = await hub.call(
        "sandbox.run_tests", {"target": "tests"}, agent_id="mamoru", allowlist=None
    )
    existing_data = existing.data or {}
    result: dict[str, Any] = {
        "existing": {
            k: existing_data.get(k)
            for k in ("passed", "failed", "errors", "summary", "failures", "backend")
        },
        "reproduced": bool(existing_data.get("failed") or existing_data.get("errors")),
        "repro_test": None,
    }
    shown = "\n\n".join(f"File {p}:\n```python\n{c}\n```" for p, c in files.items())
    out = await services().llm.structured(
        [
            ChatMessage.system(services().registry.get("mamoru").system_prompt),
            ChatMessage.user(
                "Write ONE small pytest module that reproduces this production failure. It must "
                "FAIL on the current (buggy) code and PASS once the bug is fixed. Import from the "
                "`app` package (e.g. `from app.orders import ...`). No network, no sleeps.\n\n"
                f"Error report:\n{fence(digest, source='logs', limit=2500)}\n\n{shown}"
            ),
        ],
        ReproTest,
        purpose="reproduce",
        agent_id="mamoru",
        max_tokens=1500,
        default=ReproTest(reasoning="", test_code=""),
    )
    code = out.test_code.strip()
    if "def test_" not in code:
        return result
    name = f"tests/test_repro_{incident_id.lower().replace('-', '_')}.py"
    run = await services().sandbox.run_tests(
        services().workspaces.path_for(mission_id), name, files={name: code + "\n"}, timeout_s=60
    )
    # keep it only if it fails because of assertions/exceptions in the app — not collection errors
    if run.failed >= 1 and run.errors == 0:
        await hub.call(
            "workspace.write_file",
            {"path": name, "content": code + "\n"},
            agent_id="mamoru",
            allowlist=None,
        )
        result.update(
            repro_test=name,
            reproduced=True,
            repro_reasoning=out.reasoning[:400],
            repro_failures=run.failures[:3],
        )
    else:
        result["repro_rejected"] = (
            f"generated test did not fail cleanly ({run.as_dict()['summary']})"
        )
    return result


async def recall_fix(
    signal: str, digest: str, files: dict[str, str], mission_id: str
) -> dict[str, Any] | None:
    """A Fix Library entry whose patch still applies and passes the tests, if any."""
    memory = services().extras.get("memory")
    if memory is None:
        return None
    try:
        hits = await memory.search(f"{signal}\n{digest[:600]}", ["fix_library"], k=3)
    except Exception:
        return None
    for hit in hits:
        meta = hit.get("metadata") or {}
        file, search, replace = meta.get("file"), meta.get("search"), meta.get("replace")
        if hit["score"] < 0.6 or not (file and search and replace is not None) or file not in files:
            continue
        patched = apply_search_replace(files[file], str(search), str(replace))
        if not patched.ok:
            continue
        run = await services().sandbox.run_tests(
            services().workspaces.path_for(mission_id), "tests", files={file: patched.content}
        )
        tests = run.as_dict()
        return {
            "doc_id": hit["id"],
            "score": hit["score"],
            "title": hit["title"],
            "proposal": {
                "solver_id": "fix_library",
                "strategy": "Remembered fix (Fix Library)",
                "content": f"Re-apply the fix that resolved a similar incident: {hit['title']}",
                "rationale": str(meta.get("root_cause", ""))[:500],
                "patch": {"file": file, "search": search, "replace": replace},
                "round": 0,
                "tests": {**tests, "applied": True},
            },
        }
    return None
