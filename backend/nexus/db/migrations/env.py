"""Alembic environment. The app passes its own connection (``config.attributes``); the
CLI connects to ``NEXUS_DATABASE_URL`` or the SQLite file from the settings."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from nexus.core.config import get_settings
from nexus.db.models import Base


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,  # SQLite cannot ALTER most things in place
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def sync_url() -> str:
    settings = get_settings()
    if settings.database_url:
        scheme, rest = settings.database_url.split("://", 1)
        return f"{scheme.split('+', 1)[0]}+psycopg://{rest}"
    return f"sqlite:///{settings.sqlite_path}"


given = context.config.attributes.get("connection")
if given is not None:
    run(given)
else:
    with create_engine(sync_url()).connect() as conn:
        run(conn)
