"""Apply Alembic migrations on startup, so every install (SQLite or PostgreSQL) reaches the
same schema version. Databases created before migrations existed are stamped at the
baseline first, then upgraded."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

BASELINE = "0001"
SCRIPTS = Path(__file__).parent / "migrations"


def config(connection: Connection | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(SCRIPTS))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def upgrade(connection: Connection) -> None:
    tables = set(inspect(connection).get_table_names())
    cfg = config(connection)
    if "missions" in tables and "alembic_version" not in tables:
        command.stamp(cfg, BASELINE)  # made by create_all before migrations existed
    command.upgrade(cfg, "head")
