"""Deterministic FastAPI CRUD scaffold for the Project Builder.

Live runs showed 3B models rewriting whole files badly (a ``main.py`` "repaired" down
to five lines, test files cut off mid-dict, import cycles). A CRUD service for any
entity is the proven template with ``Item`` renamed and the fields swapped, so that
part is generated here; the model's job is the spec (entity, fields, constraints)
and any constraint-specific edits, which are accepted only if they keep the
project's import contract and compile.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

TEMPLATE = Path(__file__).parent / "templates" / "fastapi_crud"
TYPES = {"str": "str", "string": "str", "int": "int", "integer": "int", "float": "float",
         "number": "float", "bool": "bool", "boolean": "bool"}  # fmt: skip
SAMPLE = {"str": '"sample"', "int": "2020", "float": "9.5", "bool": "True"}
FIELD_DEF = {
    "str": " = Field(min_length=1, max_length=200)",
    "int": " = Field(ge=0)",
    "float": " = Field(ge=0)",
    "bool": "",
}


class _ModelsOut(BaseModel):
    content: str


def entity_name(raw: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", raw) or ["Item"]
    name = "".join(w[:1].upper() + w[1:] for w in words)
    return name if name[0].isalpha() else "Item"


def parse_fields(raw: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for f in raw:
        name, _, typ = f.partition(":")
        ident = re.sub(r"\W+", "_", name.strip().lower()).strip("_")
        if ident and ident.isidentifier() and ident not in {"id", *(n for n, _ in out)}:
            out.append((ident, TYPES.get(typ.strip().lower().split("[")[0], "str")))
    return out[:8] or [("name", "str"), ("price", "float")]


def _rename(code: str, entity: str) -> str:
    lower = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    plural = lower + ("es" if lower.endswith("s") else "s")
    code = code.replace("Items", f"{entity}s").replace("items", plural)
    return code.replace("Item", entity).replace("item", lower)


def render_crud(entity_raw: str, fields_raw: list[str]) -> dict[str, str]:
    entity = entity_name(entity_raw)
    fields = parse_fields(fields_raw)
    lines = "\n".join(f"    {n}: {t}{FIELD_DEF[t]}" for n, t in fields)
    models = (
        f'"""Pydantic models for the {entity} resource."""\n\nfrom pydantic import BaseModel, Field'
        f"\n\n\nclass {entity}In(BaseModel):\n{lines}\n\n\nclass {entity}({entity}In):\n    id: int\n"
    )
    files = {
        "app/models.py": models if "Field(" in lines else models.replace(", Field", ""),
        "app/store.py": _rename((TEMPLATE / "app/store.py").read_text(), entity),
        "app/main.py": _rename((TEMPLATE / "app/main.py").read_text(), entity),
    }
    route = "/" + _rename("items", entity)
    valid = ", ".join(f'"{n}": {SAMPLE[t]}' for n, t in fields)
    first_name, first_type = fields[0]
    bad = {"str": '""', "int": "-1", "float": "-1", "bool": '"not-a-bool"'}[first_type]
    invalid = ", ".join(f'"{n}": {bad if n == first_name else SAMPLE[t]}' for n, t in fields)
    files["tests/test_api.py"] = f'''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
VALID = {{{valid}}}


def test_create_and_get():
    r = client.post("{route}", json=VALID)
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert client.get(f"{route}/{{new_id}}").json()["{first_name}"] == VALID["{first_name}"]


def test_list_update_delete():
    new_id = client.post("{route}", json=VALID).json()["id"]
    assert any(x["id"] == new_id for x in client.get("{route}").json())
    assert client.put(f"{route}/{{new_id}}", json=VALID).status_code == 200
    assert client.delete(f"{route}/{{new_id}}").status_code == 204
    assert client.get(f"{route}/{{new_id}}").status_code == 404


def test_validation():
    assert client.post("{route}", json={{{invalid}}}).status_code == 422


def test_missing_is_404():
    assert client.get("{route}/9999").status_code == 404
'''
    return files


FIELD_LIKE = re.compile(r"^\s*[A-Za-z_][\w ]*:\s*[A-Za-z]+\s*$")
INT_NAMES = re.compile(r"year|age|count|qty|quantity|stock|pages|rating|number", re.I)
FLOAT_NAMES = re.compile(r"price|cost|amount|total|salary|weight", re.I)


def normalise_fields(
    fields: list[str], constraints: list[str], task: str
) -> tuple[list[str], list[str]]:
    """Small models put "title: str" under constraints, or leave fields empty.

    Field-shaped constraints move to fields; with still no fields, a parenthesised
    list in the request ("books (title, author, year)") is used with guessed types.
    """
    moved = [c for c in constraints if FIELD_LIKE.match(c)]
    fields = [f for f in fields if FIELD_LIKE.match(f)] + moved
    constraints = [c for c in constraints if c not in moved]
    if not fields:
        for group in re.findall(r"\(([^()]+)\)", task):
            names = [n.strip() for n in group.split(",") if n.strip()]
            if len(names) >= 2 and all(re.fullmatch(r"[\w ]{1,30}", n) for n in names):
                fields = [
                    f"{n}: {'int' if INT_NAMES.search(n) else 'float' if FLOAT_NAMES.search(n) else 'str'}"
                    for n in names
                ]
                break
    return fields, constraints


async def crud_file(
    entity: str, fields: list[str], constraints: list[str], path: str, agent_id: str
) -> str:
    """One scaffold file; with constraints, the model may adapt ``app/models.py``.

    The adaptation is kept only if it compiles and still defines the classes the
    other files import; otherwise the scaffold version stands.
    """
    from nexus.core.services import services
    from nexus.llm.types import ChatMessage
    from nexus.playbooks.builder_contract import defined_names

    files = render_crud(entity, fields)
    base = files.get(path, "")
    if path != "app/models.py" or not constraints:
        return base
    name = entity_name(entity)
    out = await services().llm.structured(
        [
            ChatMessage.system(services().registry.get(agent_id).system_prompt),
            ChatMessage.user(
                f"Adapt this Pydantic module to these rules: {'; '.join(constraints)}.\n"
                f"Keep the classes {name}In and {name} and every field. Return the full file."
                f"\n```python\n{base}```"
            ),
        ],
        _ModelsOut,
        purpose="code",
        max_tokens=1200,
        agent_id=agent_id,
        default=_ModelsOut(content=base),
    )
    code = out.content.strip().removeprefix("```python").removesuffix("```").strip() + "\n"
    names = defined_names(code) or set()
    return code if {name, f"{name}In"} <= names else base


def project_summary(kind: str, entity_raw: str, fields_raw: list[str], note: str = "") -> str:
    """The Build API result in plain words: what was built, its endpoints, how to run it."""
    if kind != "fastapi_crud":
        body = "A small command-line tool with tests.\n\nRun the tests: `uv run pytest`"
        return f"{body}\n\n{note}".strip()
    entity = entity_name(entity_raw)
    fields = ", ".join(f"`{n}` ({t})" for n, t in parse_fields(fields_raw))
    route = "/" + _rename("items", entity)
    lines = [
        f"**A FastAPI service for {entity}** with fields {fields}, stored in memory.",
        "",
        "**Endpoints**",
        f"- `POST {route}`: create",
        f"- `GET {route}`: list all",
        f"- `GET {route}/{{id}}`, `PUT {route}/{{id}}`, `DELETE {route}/{{id}}`",
        "",
        "**Try it** (in the unzipped folder)",
        "- Tests: `uv run --no-project --with fastapi --with httpx --with pytest pytest`",
        "- Server: `uv run --no-project --with fastapi --with uvicorn uvicorn app.main:app` then open `/docs`",
    ]
    return "\n".join(lines) + (f"\n\n{note}" if note else "")
