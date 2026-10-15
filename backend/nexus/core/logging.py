"""Structured logging via structlog: pretty console in dev, JSON lines otherwise."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

import structlog

#: Recent log records for the Observatory's logs explorer.
LOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=1500)


def _buffer(_: Any, method: str, event_dict: Any) -> Any:
    record = {
        "ts": time.time(),
        "level": event_dict.get("level", method),
        "logger": event_dict.get("logger", ""),
        "event": str(event_dict.get("event", "")),
    }
    record["fields"] = {
        k: str(v)[:300]
        for k, v in event_dict.items()
        if k not in {"event", "level", "logger", "timestamp", "_record", "_from_structlog"}
    }
    LOG_BUFFER.append(record)
    return event_dict


def configure_logging(level: str = "INFO", *, json: bool = False) -> None:
    """Configure structlog and route stdlib logging (uvicorn, httpx) through it."""
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _buffer,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "chromadb", "mcp", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
