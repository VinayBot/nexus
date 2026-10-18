"""Import contracts between a built project's files, used by the repair loop.

A live run showed the repair step "fixing" ``app/models.py`` by rewriting it without
the ``Book`` class every other file imports, which turned one failure into another.
The repair now knows which names each file must keep defining, and a repair that
drops one is rejected.
"""

from __future__ import annotations

import ast
import re

IMPORT = re.compile(r"^from app\.(\w+) import ([\w, ()]+)", re.M)
CANNOT_IMPORT = re.compile(r"cannot import name '(\w+)' from '(app\.\w+)'")


def required_names(files: dict[str, str]) -> dict[str, dict[str, list[str]]]:
    """``{"app/models.py": {"Book": ["app/store.py", "tests/test_api.py"]}}``."""
    out: dict[str, dict[str, list[str]]] = {}
    for importer, code in files.items():
        for module, names in IMPORT.findall(code):
            target = f"app/{module}.py"
            if target == importer:
                continue
            for name in re.findall(r"\w+", names):
                out.setdefault(target, {}).setdefault(name, []).append(importer)
    return out


def defined_names(code: str) -> set[str] | None:
    """Top-level names a module defines, or None if it does not parse."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
    return names


def broken_contract(path: str, code: str, files: dict[str, str]) -> list[str]:
    """Names other files import from ``path`` that ``code`` no longer defines."""
    defined = defined_names(code)
    if defined is None:
        return ["(file does not parse)"]
    needed = required_names(files).get(path, {})
    return sorted(n for n in needed if n not in defined)


def import_culprit(output: str) -> tuple[str, str] | None:
    """``("app/models.py", "Book")`` from "cannot import name 'Book' from 'app.models'"."""
    m = CANNOT_IMPORT.search(output)
    return (m.group(2).replace(".", "/") + ".py", m.group(1)) if m else None
