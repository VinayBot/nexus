"""OpenTelemetry tracing exported to NEXUS's own SQLite trace store.

Spans: ``mission`` (root, per run) → ``node:<name>`` → ``llm:<purpose>`` /
``tool:<name>``. A BatchSpanProcessor hands finished spans to
:class:`SqliteSpanExporter` on its own thread, which writes them with a plain
``sqlite3`` connection. Phoenix (``docker compose --profile observability``) can
be added later by registering an OTLP exporter next to this one.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from nexus.core.events import mission_context


class SqliteSpanExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        rows = []
        for s in spans:
            ctx = s.get_span_context()
            if ctx is None or s.start_time is None or s.end_time is None:
                continue
            attrs = dict(s.attributes or {})
            rows.append(
                (
                    f"{ctx.span_id:016x}",
                    f"{ctx.trace_id:032x}",
                    f"{s.parent.span_id:016x}" if s.parent else None,
                    attrs.get("nexus.mission_id"),
                    s.name,
                    str(attrs.get("nexus.kind", "internal")),
                    s.start_time / 1e9,
                    s.end_time / 1e9,
                    "error" if s.status.status_code.name == "ERROR" else "ok",
                    json.dumps(attrs, default=str),
                )
            )
        if not rows:
            return SpanExportResult.SUCCESS
        try:
            with self._lock, sqlite3.connect(self.path, timeout=5) as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO trace_spans (span_id, trace_id, parent_id, mission_id, name, kind, start, end, status, attributes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
        except sqlite3.Error:
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


_provider: TracerProvider | None = None
_exporter: SqliteSpanExporter | None = None


def setup_tracing(db_path: Path) -> None:
    """Install the provider once per process; later calls just retarget the store."""
    global _provider, _exporter
    if _provider is not None and _exporter is not None:
        _exporter.path = db_path
        return
    _exporter = SqliteSpanExporter(db_path)
    _provider = TracerProvider()
    _provider.add_span_processor(BatchSpanProcessor(_exporter, schedule_delay_millis=1000))
    trace.set_tracer_provider(_provider)


def shutdown_tracing() -> None:
    global _provider
    if _provider is not None:
        _provider.force_flush()


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
