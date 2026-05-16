"""v4E: lightweight telemetry helpers.

Provides a `timed(name)` decorator + a generic `record_event(...)` helper.
All output goes through the structured JSON logger configured in v1C.

Privacy: never log secrets, tokens, request bodies, or PII. Engine names,
portfolio_ids, status bands and latency_ms are the only fields written.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Reserved keys understood by JsonFormatter in observability.py.
_DROP_KEYS = {"password", "token", "secret", "api_key", "authorization"}


def record_event(event: str, **fields: Any) -> None:
    """Emit a single telemetry event via structured logger."""
    try:
        extra: dict[str, Any] = {"telemetry_event": event}
        for key, value in (fields or {}).items():
            if key in _DROP_KEYS:
                continue
            extra[f"telemetry_{key}"] = value
        logger.info("telemetry", extra=extra)
    except Exception:
        logger.exception("telemetry record failed")


def timed(name: str, *, log_args: bool = False) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that records start/end + latency_ms for a callable.

    Logs at INFO on success, ERROR on exception. Always re-raises.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.monotonic()
            status = "ok"
            error_type: str | None = None
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                status = "error"
                error_type = exc.__class__.__name__
                raise
            finally:
                try:
                    latency_ms = round((time.monotonic() - start) * 1000.0, 2)
                    extra: dict[str, Any] = {
                        "telemetry_event": "timing",
                        "telemetry_name": name,
                        "telemetry_status": status,
                        "telemetry_latency_ms": latency_ms,
                    }
                    if error_type:
                        extra["telemetry_error_type"] = error_type
                    if log_args:
                        # Only include arg shape, never values.
                        extra["telemetry_arg_count"] = len(args)
                        extra["telemetry_kwarg_keys"] = sorted(kwargs.keys())[:8]
                    logger.info("timing", extra=extra)
                except Exception:
                    # never let telemetry crash the wrapped call
                    pass

        return wrapper

    return decorator


class TimingContext:
    """Context manager flavour for non-function code blocks."""

    def __init__(self, name: str, **fields: Any) -> None:
        self.name = name
        self.fields = fields
        self._start: float = 0.0
        self.status: str = "ok"
        self.error_type: str | None = None

    def __enter__(self) -> "TimingContext":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            self.status = "error"
            self.error_type = getattr(exc_type, "__name__", str(exc_type))
        try:
            latency_ms = round((time.monotonic() - self._start) * 1000.0, 2)
            payload = {
                "name": self.name,
                "status": self.status,
                "latency_ms": latency_ms,
            }
            if self.error_type:
                payload["error_type"] = self.error_type
            payload.update({k: v for k, v in self.fields.items() if k not in _DROP_KEYS})
            record_event("timing", **payload)
        except Exception:
            pass
        return False  # re-raise
