"""Memory Palace: long-term memory search, stats, shelves and the embedding map."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from nexus.core.services import services

router = APIRouter(prefix="/memory", tags=["memory"])


def _memory() -> Any:
    memory = services().extras.get("memory")
    if memory is None:
        raise HTTPException(503, "long-term memory is disabled")
    return memory


@router.get("/stats")
async def stats() -> dict[str, Any]:
    memory = _memory()
    return {"collections": await memory.stats(), "embedding_ok": memory.embedding_ok}


@router.get("/search")
async def search(q: str, collection: str | None = None, k: int = 6) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = await _memory().search(
        q, [collection] if collection else None, min(k, 20)
    )
    return hits


@router.get("/collections/{name}")
async def shelf(name: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        items: list[dict[str, Any]] = await _memory().list_items(name, min(limit, 200))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return items


@router.get("/map")
async def embedding_map() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = await _memory().embedding_map()
    return points
