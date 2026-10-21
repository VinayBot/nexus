"""OpenTelemetry tracing exported to NEXUS's own trace store (the ``trace_spans`` table).

Spans: ``mission`` (root, per run) → ``node:<name>`` → ``llm:<purpose>`` /
``tool:<name>``. A BatchSpanProcessor hands finished spans to :class:`DbSpanExporter`
on its own thread, which writes them through a small *synchronous* SQLAlchemy engine to
the same database as the rest of the app data (SQLite or PostgreSQL), so the
Observatory reads them back in either mode. Phoenix
(``docker compose --profile observability``) can be added by registering an OTLP
exporter next to this one.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from nexus.core.events import mission_context


def sync_url(target: Path | str) -> str:
    """The app's database as a synchronous SQLAlchemy URL (the exporter runs on a thread)."""
    if isinstance(target, Path):
        return f"sqlite:///{target}"
    scheme, rest = target.split("://", 1)
    driver = "psycopg" if scheme.startswith("postgresql") else "pysqlite"
    return f"{scheme.split('+', 1)[0]}+{driver}://{rest}"


class DbSpanExporter(SpanExporter):
    def __init__(self, target: Path | str) -> None:
        self._lock = threading.Lock()
        self._engine: Engine = create_engine(sync_url(target), pool_pre_ping=True)

    def retarget(self, target: Path | str) -> None:
        with self._lock:
            self._engine.dispose()
            self._engine = create_engine(sync_url(target), pool_pre_ping=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        from nexus.db.models import TraceSpanRow

        rows = []
        for s in spans:
            ctx = s.get_span_context()
            if ctx is None or s.start_time is None or s.end_time is None:
                continue
            attrs = dict(s.attributes or {})
            rows.append(
                {
                    "span_id": f"{ctx.span_id:016x}",
                    "trace_id": f"{ctx.trace_id:032x}",
                    "parent_id": f"{s.parent.span_id:016x}" if s.parent else None,
                    "mission_id": attrs.get("nexus.mission_id"),
                    "name": s.name[:120],
                    "kind": str(attrs.get("nexus.kind", "internal"))[:20],
                    "start": s.start_time / 1e9,
                    "end": s.end_time / 1e9,
                    "status": "error" if s.status.status_code.name == "ERROR" else "ok",
                    "attributes": json.loads(json.dumps(attrs, default=str)),
                }
            )
        if not rows:
            return SpanExportResult.SUCCESS
        with self._lock:
            engine = self._engine
            if engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert  # type: ignore[assignment]
            try:
                with engine.begin() as conn:
                    conn.execute(insert(TraceSpanRow).values(rows).on_conflict_do_nothing())
            except SQLAlchemyError:
                return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._engine.dispose()


_provider: TracerProvider | None = None
_exporter: DbSpanExporter | None = None


def setup_tracing(target: Path | str) -> None:
    """Install the provider once per process; later calls just retarget the store."""
    global _provider, _exporter
    if _provider is not None and _exporter is not None:
        _exporter.retarget(target)
        return
    _exporter = DbSpanExporter(target)
    _provider = TracerProvider()
    _provider.add_span_processor(BatchSpanProcessor(_exporter, schedule_delay_millis=1000))
    trace.set_tracer_provider(_provider)


def flush_tracing() -> None:
    """Write buffered spans now (on shutdown, and before reading traces in tests)."""
    if _provider is not None:
        _provider.force_flush()


def shutdown_tracing() -> None:
    flush_tracing()


tracer = trace.get_tracer("nexus")


@contextmanager
def span(name: str, kind: str, **attributes: Any) -> Iterator[trace.Span]:
    """Start a span tagged with the current mission (no-op exporter if tracing is off)."""
    ctx = mission_context.get()
    attrs: dict[str, Any] = {
        "nexus.kind": kind,
        **{f"nexus.{k}": v for k, v in attributes.items() if v is not None},
    }
    if ctx is not None:
        attrs["nexus.mission_id"] = ctx.mission_id
    with tracer.start_as_current_span(name, attributes=attrs) as s:
        yield s
