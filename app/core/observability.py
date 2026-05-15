"""Observability primitives: Sentry init, request ID, latency logging, structured logs.

Designed to fail-soft:
- Missing `SENTRY_DSN` (or missing `sentry-sdk`) does not break startup.
- Middlewares never let logging or context-management exceptions reach callers.

Privacy / safety contract:
- Never logs Authorization, cookies, request body, query string, DATABASE_URL,
  Anthropic / Telegram tokens, or password fields.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import is_development_env, runtime_environment, settings

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_request_id_ctx: ContextVar[str] = ContextVar("ixai_request_id", default="-")

# Reserved keys on LogRecord; anything else passed via `extra={...}` is rendered.
_RESERVED_LOG_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "request_id",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def get_request_id() -> str:
    return _request_id_ctx.get()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class RequestContextFilter(logging.Filter):
    """Inject the active request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class _KeyValueFormatter(logging.Formatter):
    """Human-readable formatter for development logs."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        base = (
            f"{ts} {record.levelname:<7} "
            f"[{getattr(record, 'request_id', '-')}] "
            f"{record.name}: {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class _JsonFormatter(logging.Formatter):
    """JSON-friendly formatter for production logs (one JSON object per line)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_KEYS:
                continue
            payload.setdefault(key, value)
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            # Final defensive fallback: never crash logging.
            return f"{payload.get('ts')} {payload.get('level')} {payload.get('msg')}"


def configure_logging() -> None:
    """Idempotently configure root logging for the runtime environment."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_ixai_managed", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if is_development_env():
        handler.setFormatter(_KeyValueFormatter())
    else:
        handler.setFormatter(_JsonFormatter())
    handler.addFilter(RequestContextFilter())
    handler._ixai_managed = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    level_name = (os.getenv("LOG_LEVEL") or settings.LOG_LEVEL or "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------
def init_sentry() -> bool:
    """Best-effort Sentry init. Returns True iff Sentry was enabled.

    Safe to call when SENTRY_DSN is unset; safe to call when sentry-sdk is not
    installed. Never raises.
    """
    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn:
        logger.info("Sentry disabled (no SENTRY_DSN configured)")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR,
        )
        sentry_sdk.init(
            dsn=dsn,
            environment=runtime_environment() or "unknown",
            traces_sample_rate=float(settings.SENTRY_TRACES_SAMPLE_RATE or 0),
            profiles_sample_rate=float(settings.SENTRY_PROFILES_SAMPLE_RATE or 0),
            send_default_pii=False,
            integrations=[sentry_logging],
        )
        logger.info(
            "Sentry initialised",
            extra={
                "traces_sample_rate": float(settings.SENTRY_TRACES_SAMPLE_RATE or 0),
                "profiles_sample_rate": float(settings.SENTRY_PROFILES_SAMPLE_RATE or 0),
            },
        )
        return True
    except Exception:
        logger.exception("Sentry init failed; continuing without error tracking")
        return False


# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate a request id, expose it via response header + ContextVar."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        if incoming and 0 < len(incoming) <= 200:
            rid = incoming
        else:
            rid = uuid.uuid4().hex
        token = _request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            try:
                _request_id_ctx.reset(token)
            except Exception:
                pass
        try:
            response.headers[REQUEST_ID_HEADER] = rid
        except Exception:
            pass
        return response


class RequestLatencyMiddleware(BaseHTTPMiddleware):
    """Log structured per-request latency / status. Never log auth, cookies, body, query."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            try:
                latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
                logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": _sanitise_path(request.url.path),
                        "status_code": status_code,
                        "latency_ms": latency_ms,
                        "client_ip": _client_ip(request),
                        "user_agent": _short_ua(request.headers.get("user-agent", "")),
                        "request_id": get_request_id(),
                    },
                )
            except Exception:
                # Never let logging crash the response.
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _short_ua(ua: str) -> str:
    ua = str(ua or "").strip()
    return ua[:80] if ua else "-"


def _sanitise_path(path: str) -> str:
    if "?" in path:
        return path.split("?", 1)[0]
    return path
