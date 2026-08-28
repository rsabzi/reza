"""Database configuration and request-scoped sessions."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class shared by core and optional module models."""


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent_core.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """SQLite does not enforce foreign keys unless enabled per connection."""

    if not dbapi_connection.__class__.__module__.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create every model table and add columns introduced after first deploy."""

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns(
        {
            "tasks": {"due_at": "DATETIME"},
        }
    )


def _ensure_sqlite_columns(columns_by_table: dict[str, dict[str, str]]) -> None:
    """ALTER TABLE ... ADD COLUMN for models added to existing installs.

    ``create_all`` only creates missing tables; SQLite has no built-in
    migration, so columns added after the first deployment are appended here.
    """

    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        for table_name, columns in columns_by_table.items():
            existing = {
                row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})")
            }
            if not existing:
                continue  # table absent (fresh create_all already made it)
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )
