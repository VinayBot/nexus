"""The LangGraph checkpointer: SQLite next to the app data, or PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver

from nexus.core.config import Settings


def psycopg_url(database_url: str) -> str:
    """``postgresql+asyncpg://…`` (SQLAlchemy) → ``postgresql://…`` (psycopg)."""
    scheme, rest = database_url.split("://", 1)
    return f"{scheme.split('+', 1)[0]}://{rest}"


@asynccontextmanager
async def open_checkpointer(settings: Settings) -> AsyncIterator[BaseCheckpointSaver[str]]:
    if settings.uses_postgres and settings.database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(psycopg_url(settings.database_url)) as pg:
            await pg.setup()  # idempotent: creates or migrates the checkpoint tables
            yield pg
        return
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoints_path)) as saver:
        yield saver
