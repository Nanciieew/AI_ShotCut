"""
Database session management.

Supports SQLite (development) and PostgreSQL (production) switching
via the DATABASE_URL environment variable.
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/app.db",
)

_engine = create_async_engine(DATABASE_URL, echo=False)

_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Yield an async database session.

    Usage (FastAPI dependency)::

        from core.database.session import get_db

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with _async_session_factory() as session:
        yield session


async def check_db_connection() -> bool:
    """Test database connectivity. Returns True if reachable."""
    try:
        async with _engine.connect() as conn:
            await conn.execute(
                # Use a simple connectivity check that works with SQLite and PostgreSQL
                __import__("sqlalchemy").text("SELECT 1")
            )
        return True
    except Exception:
        return False


async def init_db() -> None:
    """Create all tables from SQLAlchemy metadata.

    Import models before calling this so they register on Base.metadata.
    """
    from core.database.models import Base  # noqa: F811

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
