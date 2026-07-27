"""Pytest configuration and shared fixtures.

Provides:
  - async test support
  - in-memory SQLite database for testing
  - test client for FastAPI
  - temp directories for storage
"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.database.models import Base
from apps.api.main import create_app


# ---------------------------------------------------------------------------
# Event loop (session scope)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def test_engine():
    """In-memory SQLite engine shared across all tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Fresh database session per test, rolled back after."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI app."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Temporary directories
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_storage_dir() -> Path:
    """Temporary directory for artifact storage tests."""
    with tempfile.TemporaryDirectory(prefix="test_storage_") as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_data_dir() -> Path:
    """Temporary directory for general test data."""
    with tempfile.TemporaryDirectory(prefix="test_data_") as tmp:
        yield Path(tmp)


# ---------------------------------------------------------------------------
# Test fixtures path
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
