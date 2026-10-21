"""What the Project Builder plans (``ProjectSpec``) and the proven templates it builds
from. The model decides *what* is built; the template decides *where* each file goes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

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


def template_files(kind: str) -> dict[str, str]:
    root = TEMPLATES / kind
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*.py"))
        if p.name != "__init__.py"
    }


def template_layout(kind: str) -> list[FileSpec]:
    """The template's own file layout, with dependencies read from its imports.

    Live runs showed 3B models inventing layouts (e.g. ``Book`` defined in two modules
    that import each other); the single-file repair loop cannot fix an import cycle.
    The model still decides *what* is built (entity, fields, constraints); the
    proven template decides *where* it goes.
    """
    files = template_files(kind)
    out = []
    for path, code in files.items():
        deps = [
            f"app/{m}.py"
            for m in re.findall(r"^from app\.(\w+) import", code, re.M)
            if f"app/{m}.py" in files and f"app/{m}.py" != path
        ]
        purpose = (
            "tests" if path.startswith("tests/") else f"adapt {Path(path).name} from the template"
        )
        out.append(FileSpec(path=path, purpose=purpose, depends_on=deps))
    return out


def slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:40]
