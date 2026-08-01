"""FastAPI middleware for request-id injection and request logging."""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging.config import get_logger
from core.logging.context import clear_task_context, set_task_context

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Injects a unique request_id into every HTTP request context.

    Also logs request method, path, status, and duration.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        set_task_context(request_id=request_id)

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Don't log sensitive paths
        path = request.url.path
        if not path.startswith("/health"):
            logger.info(
                "request_completed",
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        clear_task_context()
        response.headers["X-Request-ID"] = request_id
        return response
