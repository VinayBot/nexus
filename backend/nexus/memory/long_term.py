"""Long-term memory on ChromaDB (embedded, persistent).

Collections: ``fix_library`` (incidents + fixes), ``missions`` (mission summaries),
``docs`` (project documentation for RAG and the guide), ``lessons`` (agent lessons
and owner feedback). Embeddings come from the local embedding model through the
LLM gateway, so the Resource Governor and retries apply.

Only the backend process opens this store (two processes on one embedded Chroma
directory leave each other's index stale). Chroma's client is synchronous, so
calls run in a worker thread.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from nexus.core.event_types import MemoryRecalled
from nexus.core.events import emit
from nexus.core.logging import get_logger

log = get_logger(__name__)

COLLECTIONS = ("fix_library", "missions", "docs", "lessons")


class MemoryUnavailableError(RuntimeError):
    pass


Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]


class LongTermMemory:
    def __init__(self, path: Path | None, embed: Embedder) -> None:
        settings = ChromaSettings(anonymized_telemetry=False, allow_reset=True)
        self.client = (
            chromadb.PersistentClient(path=str(path), settings=settings)
            if path
            else chromadb.EphemeralClient(settings)
        )
        self.embed = embed
        self._cols = {
            name: self.client.get_or_create_collection(
                name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
            )
            for name in COLLECTIONS
        }
        self.embedding_ok = True

    def _col(self, name: str) -> Any:
        if name not in self._cols:
            raise KeyError(f"unknown collection '{name}' (have {', '.join(COLLECTIONS)})")
        return self._cols[name]

    async def _vectors(self, texts: list[str]) -> list[list[float]] | None:
        try:
            vecs = await self.embed(texts)
            self.embedding_ok = True
            return vecs
        except Exception as exc:  # noqa: BLE001 - embedding model down → keyword fallback
            log.warning("memory.embed_failed", error=str(exc))
            self.embedding_ok = False
            return None

    async def add(
        self,
        collection: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        doc_id = doc_id or uuid.uuid4().hex[:16]
        meta = {
            k: v for k, v in (metadata or {}).items() if isinstance(v, str | int | float | bool)
        }
        meta.setdefault("ts", time.time())
        meta.setdefault("title", text.strip().splitlines()[0][:120] if text.strip() else doc_id)
        vecs = await self._vectors([text])
        col = self._col(collection)
        if vecs is None:
            raise MemoryUnavailableError("embedding model unavailable; memory not stored")
        await asyncio.to_thread(
            col.upsert, ids=[doc_id], documents=[text], embeddings=vecs, metadatas=[meta]
        )
        return doc_id

    async def search(
        self,
        query: str,
        collections: list[str] | None = None,
        k: int = 4,
        *,
        emit_event: bool = True,
    ) -> list[dict[str, Any]]:
        names = collections or list(COLLECTIONS)
        vecs = await self._vectors([query])
        hits: list[dict[str, Any]] = []
        for name in names:
            col = self._col(name)
            if await asyncio.to_thread(col.count) == 0:
                continue
            if vecs is not None:
                res = await asyncio.to_thread(
                    col.query,
                    query_embeddings=vecs,
                    n_results=min(k, col.count()),
                    include=["documents", "metadatas", "distances"],
                )
                for i, doc_id in enumerate(res["ids"][0]):
                    hits.append(
                        {
                            "id": doc_id,
                            "collection": name,
                            "title": str((res["metadatas"][0][i] or {}).get("title", doc_id)),
                            "text": res["documents"][0][i],
                            "score": round(1 - float(res["distances"][0][i]), 3),
                            "metadata": res["metadatas"][0][i] or {},
                        }
                    )
            else:
                hits.extend(await self._keyword(col, name, query, k))
        hits.sort(key=lambda h: h["score"], reverse=True)
        hits = hits[:k]
        if emit_event:
            emit(
                "memory.recalled",
                MemoryRecalled(
                    collection=",".join(names),
                    query=query[:200],
                    hits=[
                        {
                            "id": h["id"],
                            "collection": h["collection"],
                            "title": h["title"],
                            "score": h["score"],
                        }
                        for h in hits
                    ],
                ),
            )
        return hits

    async def _keyword(self, col: Any, name: str, query: str, k: int) -> list[dict[str, Any]]:
        words = re.findall(r"[A-Za-z0-9_]{4,}", query.lower())[:5]
        out: dict[str, dict[str, Any]] = {}
        for w in words:
            res = await asyncio.to_thread(
                col.get,
                where_document={"$contains": w},
                limit=k,
                include=["documents", "metadatas"],
            )
            for i, doc_id in enumerate(res["ids"]):
                hit = out.setdefault(
                    doc_id,
                    {
                        "id": doc_id,
                        "collection": name,
                        "title": str((res["metadatas"][i] or {}).get("title", doc_id)),
                        "text": res["documents"][i],
                        "score": 0.0,
                        "metadata": res["metadatas"][i] or {},
                    },
                )
                hit["score"] = round(hit["score"] + 1 / len(words), 3)
        return list(out.values())

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        res = await asyncio.to_thread(
            self._col(collection).get, ids=[doc_id], include=["documents", "metadatas"]
        )
        if not res["ids"]:
            return None
        return {
            "id": doc_id,
            "collection": collection,
            "text": res["documents"][0],
            "metadata": res["metadatas"][0] or {},
        }

    async def list_items(self, collection: str, limit: int = 50) -> list[dict[str, Any]]:
        res = await asyncio.to_thread(
            self._col(collection).get, limit=limit, include=["documents", "metadatas"]
        )
        items = [
            {
                "id": i,
                "collection": collection,
                "title": str((m or {}).get("title", i)),
                "text": d,
                "metadata": m or {},
            }
            for i, d, m in zip(res["ids"], res["documents"], res["metadatas"], strict=False)
        ]
        items.sort(key=lambda x: float(x["metadata"].get("ts", 0)), reverse=True)
        return items

    async def stats(self) -> dict[str, int]:
        return {name: await asyncio.to_thread(col.count) for name, col in self._cols.items()}

    async def embedding_map(self, limit_per_collection: int = 150) -> list[dict[str, Any]]:
        """2-D PCA projection of every stored vector (computed server-side, numpy only)."""
        points: list[dict[str, Any]] = []
        vectors: list[list[float]] = []
        for name, col in self._cols.items():
            res = await asyncio.to_thread(
                col.get, limit=limit_per_collection, include=["embeddings", "metadatas"]
            )
            embs = res.get("embeddings")
            if embs is None:
                continue
            metas = res.get("metadatas") or [{}] * len(res["ids"])
            for i, doc_id in enumerate(res["ids"]):
                vectors.append(list(embs[i]))
                points.append(
                    {
                        "id": doc_id,
                        "collection": name,
                        "title": str((metas[i] or {}).get("title", doc_id)),
                    }
                )
        if len(vectors) < 2:
            for p in points:
                p.update(x=0.0, y=0.0)
            return points
        dims = {len(v) for v in vectors}
        if len(dims) > 1:  # mixed embedding sizes (model changed): project the majority only
            common = max(dims, key=lambda d: sum(len(v) == d for v in vectors))
            keep = [i for i, v in enumerate(vectors) if len(v) == common]
            vectors = [vectors[i] for i in keep]
            points = [points[i] for i in keep]
        x = np.asarray(vectors, dtype=np.float32)
        x = x - x.mean(axis=0)
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        coords = x @ vt[:2].T
        span = np.abs(coords).max(axis=0)
        span[span == 0] = 1
        coords = coords / span
        for p, (cx, cy) in zip(points, coords.tolist(), strict=True):
            p.update(x=round(cx, 4), y=round(cy, 4))
        return points


def project_doc_paths() -> list[Path]:
    """The project's own docs the guide and knowledge search are grounded in."""
    from nexus.core.config import PROJECT_ROOT

    docs = PROJECT_ROOT / "docs"
    return [
        PROJECT_ROOT / "README.md",
        *sorted(docs.glob("*.md")),
        *sorted((docs / "adr").glob("*.md")),
    ]


def chunk_markdown(text: str, max_chars: int = 900) -> list[tuple[str, str]]:
    """Split markdown by headings into (title, chunk) pairs of bounded size."""
    sections: list[tuple[str, str]] = []
    title, buf = "Introduction", list[str]()
    for line in text.splitlines():
        if line.startswith("#"):
            if buf:
                sections.append((title, "\n".join(buf).strip()))
            title, buf = line.lstrip("# ").strip() or title, []
        else:
            buf.append(line)
    if buf:
        sections.append((title, "\n".join(buf).strip()))
    out: list[tuple[str, str]] = []
    for t, body in sections:
        if not body:
            continue
        for i in range(0, len(body), max_chars):
            out.append((t, body[i : i + max_chars]))
    return out


async def index_docs(memory: LongTermMemory, paths: list[Path]) -> int:
    """Index markdown docs into the ``docs`` collection (idempotent by content hash)."""
    count = 0
    for path in paths:
        if not path.exists():
            continue
        for title, chunk in chunk_markdown(path.read_text(errors="ignore")):
            digest = hashlib.sha256(f"{path.name}:{title}:{chunk}".encode()).hexdigest()[:16]
            if await memory.get("docs", digest):
                continue
            await memory.add(
                "docs",
                f"{title}\n{chunk}",
                {"title": f"{path.name} — {title}", "source": path.name},
                doc_id=digest,
            )
            count += 1
    return count
