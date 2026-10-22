"""Simulation mode for the code missions (Fix service, Solve ticket).

A real model reads the numbered files the solver is shown and proposes one line-range
edit. The simulation does the same for the bugs it knows: every Chaos Lab switch (a
known good/bad line pair) and the seeded tickets T-101 and T-103. Everything after the
proposal stays real: the patch is applied in a workspace, tested in the sandbox, reviewed,
approved and verified. Unknown problems get an honest no-op edit, so the mission fails
validation instead of pretending.
"""

from __future__ import annotations

import json
import re

from nexus.llm.types import LLMRequest

FILE = re.compile(r"File (\S+) \(line numbers on the left\):\n```\n(.*?)```", re.S)
LINE = re.compile(r"^\s*(\d+)\| ?(.*)$")

WELCOME5_TEST = """from app.orders import apply_discount


def test_welcome5_gives_five_percent():
    assert apply_discount(100.0, "WELCOME5") == 95.0
    assert apply_discount(100.0, "welcome5") == 95.0
"""

THRESHOLD_TEST = """from app.orders import compute_total


def test_orders_of_exactly_40_ship_free():
    order = {"items": [{"sku": "A", "price": 40.0, "qty": 1}], "discount_code": None}
    assert compute_total(order)["shipping"] == 0.0
"""


def shown_files(req: LLMRequest) -> dict[str, dict[int, str]]:
    """The numbered files in the solver's prompt: path → {line number: code}."""
    text = req.messages[-1].content if req.messages else ""
    files: dict[str, dict[int, str]] = {}
    for path, body in FILE.findall(text):
        lines = {}
        for raw in body.splitlines():
            m = LINE.match(raw)
            if m:
                lines[int(m.group(1))] = m.group(2)
        files[path] = lines
    return files


def _edit(path: str, line: int, replacement: str, why: str) -> str:
    return json.dumps(
        {
            "rationale": why,
            "file": path,
            "start_line": line,
            "end_line": line,
            "replacement": replacement,
        }
    )


def code_fix(req: LLMRequest) -> str:
    """One line-range edit for a known bug, found in the files the solver was shown."""
    from nexus.playbooks.demo_service import SWITCHES

    files = shown_files(req)
    problem = req.messages[-1].content.split("File ", 1)[0] if req.messages else ""
    wants_welcome5 = "WELCOME5" in problem
    wants_threshold = "threshold" in problem.lower() and "40" in problem
    for path, lines in files.items():
        for no, code in lines.items():
            for sw in SWITCHES.values():
                if path == sw.file and code == sw.replace:  # the injected bug
                    why = f"Root cause: {sw.symptom.lower()}. Restore the correct line."
                    return _edit(path, no, sw.search, f"{why} (simulation)")
            if wants_welcome5 and code.startswith("DISCOUNTS = {") and "WELCOME5" not in code:
                fixed = code.rstrip().removesuffix("}") + ', "WELCOME5": 0.05}'
                return _edit(path, no, fixed, "Add the WELCOME5 code (5%) (simulation)")
            if wants_threshold and code.startswith("FREE_SHIPPING_OVER = ") and "40" not in code:
                return _edit(
                    path, no, "FREE_SHIPPING_OVER = 40.0", "Lower the threshold to 40 (simulation)"
                )
    path, lines = next(iter(files.items()), ("app/orders.py", {1: ""}))
    first = min(lines) if lines else 1
    return _edit(
        path,
        first,
        lines.get(first, ""),
        "Simulation has no scripted fix for this problem: no change (validation will say so).",
    )


def requirements(req: LLMRequest) -> str:
    """Ticket → requirements and an acceptance test (scripted for the seeded tickets)."""
    text = " ".join(m.content for m in req.messages)
    if "WELCOME5" in text:
        return json.dumps(
            {
                "summary": "Add the WELCOME5 discount code for 5% off.",
                "acceptance_criteria": ["WELCOME5 gives 5% off", "codes are case-insensitive"],
                "likely_files": ["app/config.py"],
                "acceptance_test": WELCOME5_TEST,
            }
        )
    if "threshold" in text.lower() and "40" in text:
        return json.dumps(
            {
                "summary": "Orders of 40 or more ship free.",
                "acceptance_criteria": ["an order of exactly 40 ships free"],
                "likely_files": ["app/config.py"],
                "acceptance_test": THRESHOLD_TEST,
            }
        )
    return json.dumps(
        {
            "summary": "Requirements could not be scripted in simulation.",
            "acceptance_criteria": ["see the ticket"],
            "likely_files": [],
            "acceptance_test": "",
        }
    )
