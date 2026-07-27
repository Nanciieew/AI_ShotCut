#!/usr/bin/env python3
"""
Database initialization script.

Creates all tables defined in core.database.models.

Usage:
    python scripts/initialize_database.py
"""

import asyncio
import sys

from core.database.session import init_db


async def main() -> None:
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully.")


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
