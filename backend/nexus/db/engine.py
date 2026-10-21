"""Async SQLAlchemy engine for app data.

SQLite by default (WAL mode so readers never block the writer); PostgreSQL when
``NEXUS_DATABASE_URL`` is set, for several backend replicas sharing one store.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, target: Path | str, *, pooled: bool = True) -> None:
        if isinstance(target, Path):
            target.parent.mkdir(parents=True, exist_ok=True)
            self.engine: AsyncEngine = create_async_engine(f"sqlite+aiosqlite:///{target}")

            @event.listens_for(self.engine.sync_engine, "connect")
            def _pragmas(dbapi_conn: Any, _record: Any) -> None:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()

        elif pooled:
            self.engine = create_async_engine(
                target, pool_size=10, max_overflow=10, pool_pre_ping=True
            )
        else:  # tests drive the app from several event loops; asyncpg pools are per loop
            from sqlalchemy.pool import NullPool

            self.engine = create_async_engine(target, poolclass=NullPool)
        self.dialect = self.engine.dialect.name  # "sqlite" or "postgresql"
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        """Bring the schema to the latest migration (``nexus/db/migrations``)."""
        from nexus.db.migrate import upgrade

        async with self.engine.connect() as conn:
            await conn.run_sync(upgrade)
            await conn.commit()

    def insert(self, table: Any) -> Any:
        """``INSERT`` with ``on_conflict_do_nothing`` for this database's dialect."""
        if self.dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            return pg_insert(table)
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return sqlite_insert(table)

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("select 1"))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessions() as s:
            try:
                yield s
                await s.commit()
            except Exception:  # roll back whatever failed, then re-raise
                await s.rollback()
                raise

    async def close(self) -> None:
        await self.engine.dispose()
