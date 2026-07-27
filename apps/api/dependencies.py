"""
Shared FastAPI dependencies.

Provides dependency injection for:
  - Database sessions
  - Configuration
  - Storage backend
"""

from core.database.session import get_db as _get_db

# Re-export the database session dependency
get_db = _get_db
