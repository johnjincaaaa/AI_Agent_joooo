"""
ASGI middleware for Jingent AI — request ID tracing + access log + request log DB.

Every request gets a unique `request_id` (uuid8) attached to the
ASGI scope and returned as `X-Request-ID` header.  If the client
sends `X-Request-ID` in (e.g. from a gateway), that value is reused
for cross-system tracing.

Non-static requests are also recorded into `request_logs` (IP / UA /
referer / status / elapsed / user identity) on a background thread, so
the admin console can show visitors & registered users with headers.
"""
from __future__ import annotations

import hashlib
import threading
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

# 请求日志异步写库（后台线程，绝不阻塞请求）
_log_db_thread = None
_log_db_queue = []  # type: list[dict]
_log_db_lock = threading.Lock()


def _visitor_key(ip: str, ua: str) -> str:
    """访客去重键：sha256(ua|ip) 前 32 位。"""
    raw = f"{ua or ''}|{ip or ''}".encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:32]


def _flush_request_logs():
    """后台线程：把队列里的请求日志批量写入 SQLite。"""
    from app.core.db import SessionLocal, RequestLog
    while True:
        with _log_db_lock:
            if not _log_db_queue:
                time.sleep(0.5)
                continue
            batch = _log_db_queue[:300]
            del _log_db_queue[:300]
        db = SessionLocal()
        try:
            for item in batch:
                try:
                    db.add(RequestLog(**item))
                except Exception:
                    pass
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()


def _ensure_log_writer():
    global _log_db_thread
    if _log_db_thread is None or not _log_db_thread.is_alive():
        _log_db_thread = threading.Thread(target=_flush_request_logs, daemon=True)
        _log_db_thread.start()


def _record_request_log(entry: dict):
    """入队一条请求日志（异步、非阻塞、失败不影响请求）。"""
    try:
        with _log_db_lock:
            _log_db_queue.append(entry)
            if len(_log_db_queue) > 5000:
                del _log_db_queue[:1000]  # 兜底限流，避免内存暴涨
        _ensure_log_writer()
    except Exception:
        pass


def _resolve_user_id(request: Request) -> int:
    """从 Authorization header / cookie 解析用户 id（轻量，不依赖 Depends）。"""
    try:
        from jose import jwt
        from app.config import SECRET_KEY, ALGORITHM
        from app.core.token_utils import TOKEN_COOKIE_KEY

        token = None
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            token = request.cookies.get(TOKEN_COOKIE_KEY) or request.cookies.get("auth_token")
        if not token:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("user_id")
        if uid is None:
            return None
        return int(uid)
    except Exception:
        return None


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

            # 异步记录请求日志（后台线程写库，不阻塞响应）
            _record_request_log({
                "request_id": request_id,
                "method": method,
                "path": path,
                "ip": client if client != "-" else None,
                "user_agent": (request.headers.get("user-agent") or "")[:500] or None,
                "referer": (request.headers.get("referer") or "")[:500] or None,
                "user_id": _resolve_user_id(request),
                "visitor_key": _visitor_key(client, request.headers.get("user-agent") or ""),
                "status_code": status,
                "elapsed_ms": elapsed_ms,
            })

        return response


def add_request_middleware(app: ASGIApp) -> None:
    """Register all middlewares in this module onto `app`."""
    app.add_middleware(RequestIdMiddleware)


def current_request_id(request: Request) -> str:
    """Utility: pull request_id from request scope (for handlers to log manually)."""
    return request.scope.get("request_id", "-")
