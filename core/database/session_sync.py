"""
Synchronous database session for Celery workers.

Celery tasks are plain def functions (not async), so they
cannot use the async session factory from core.database.session.
This module provides a synchronous alternative via SQLAlchemy's
synchronous engine + sessionmaker.
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Derive a sync URL from the async DATABASE_URL.
# For SQLite:  sqlite+aiosqlite:///./data/app.db  →  sqlite:///./data/app.db
# For PostgreSQL: postgresql+asyncpg://...  →  postgresql://...
DATABASE_URL_ASYNC = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/app.db",
)

DATABASE_URL_SYNC = (
    DATABASE_URL_ASYNC
    .replace("+aiosqlite", "")
    .replace("+asyncpg", "+psycopg2")
)

_sync_engine = create_engine(
    DATABASE_URL_SYNC,
    echo=False,
    # SQLite needs this for cross-thread access
    connect_args=(
        {"check_same_thread": False}
        if "sqlite" in DATABASE_URL_SYNC
        else {}
    ),
)

SyncSessionFactory = sessionmaker(
    bind=_sync_engine,
    expire_on_commit=False,
)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Yield a synchronous SQLAlchemy Session.

    Usage in Celery tasks::

        from core.database.session_sync import get_sync_session

        with get_sync_session() as session:
            repo = TaskRepository(session)
            repo.update_status(task_id, "RUNNING")
            session.commit()
    """
    session = SyncSessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_engine():
    """Return the synchronous engine (e.g. for init_db_sync)."""
    return _sync_engine
