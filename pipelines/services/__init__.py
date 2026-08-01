"""Pipeline service implementations.

Each service orchestrates a complete model pipeline step,
calling core/media or model adapters without directly
accessing Celery, Redis, or FastAPI.
"""
