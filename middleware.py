"""
ASGI middleware for Jingent AI — request ID tracing + access log.

Every request gets a unique `request_id` (uuid8) attached to the
ASGI scope and returned as `X-Request-ID` header.  If the client
sends `X-Request-ID` in (e.g. from a gateway), that value is reused
for cross-system tracing.

Usage:
    from middleware import add_request_middleware
    add_request_middleware(app)
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("jingent.access")

# Paths we don't spam the access log with (every 1s healthchecks etc.)
_NO_LOG_PATHS = {"/health", "/favicon.ico", "/static", "/uploads", "/openapi.json", "/docs", "/redoc"}


class RequestContext:
    """Binds request_id → current call stack via threading.local-ish contextvar.

    (Kept simple; if you later upgrade to structured logging with JSON,
    move request_id into a ContextVar and use a logging filter to
    inject it into every LogRecord automatically.)
    """


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()

        # Inherit or generate request ID
        incoming_req_id = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
        request_id = incoming_req_id or uuid.uuid4().hex[:12]
        # Attach to ASGI scope so downstream handlers can pull it
        request.scope["request_id"] = request_id

        # Skip no-log paths quickly
        path = request.url.path
        method = request.method
        client = request.client.host if request.client else "-"
        skip_log = any(path.startswith(p) for p in _NO_LOG_PATHS)

        try:
            response: Response = await call_next(request)
        except Exception:
            # Log even unhandled exceptions so we know what crashed
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "req=%s | %s %s | %s | %dms | 500 UNHANDLED",
                request_id, method, path, client, elapsed_ms,
                exc_info=True,
            )
            raise

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id

        if not skip_log:
            # INFO for 2xx/3xx, WARN for 4xx, ERROR for 5xx
            if status < 400:
                logger.info(
                    "req=%s | %s %s | %s | %dms | %d",
                    request_id, method, path, client, elapsed_ms, status,
                )
            elif status < 500:
                logger.warning(
                    "req=%s | %s %s | %s | %dms | %d",
                    request_id, method, path, client, elapsed_ms, status,
                )
            else:
                logger.error(
                    "req=%s | %s %s | %s | %dms | %d",
                    request_id, method, path, client, elapsed_ms, status,
                )

        return response


def add_request_middleware(app: ASGIApp) -> None:
    """Register all middlewares in this module onto `app`."""
    app.add_middleware(RequestIdMiddleware)


def current_request_id(request: Request) -> str:
    """Utility: pull request_id from request scope (for handlers to log manually)."""
    return request.scope.get("request_id", "-")
