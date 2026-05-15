"""Regression tests for Engineering Hardening Pack v1C (Observability).

Covers:
- Sentry init is fail-safe when SENTRY_DSN is absent.
- RequestIDMiddleware propagates an incoming X-Request-ID and generates one
  when missing.
- /readyz returns the new `app` field on both success and failure.
- RequestLatencyMiddleware does not crash the response when the handler raises.
- configure_logging is idempotent.
- Existing dashboard contract tests still pass (covered by the wider suite).
"""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------
def test_sentry_disabled_when_dsn_missing(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    # Settings was loaded before this test ran; force the attribute too.
    from app.core import config as cfg
    from app.core import observability

    monkeypatch.setattr(cfg.settings, "SENTRY_DSN", None, raising=False)

    enabled = observability.init_sentry()
    assert enabled is False


def test_app_import_does_not_require_sentry_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    # Re-importing the FastAPI app must succeed cleanly when no DSN is set.
    from app.main import app

    assert app.title == "IXAI Agent"


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------
def test_request_id_generated_when_header_missing():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        rid = response.headers.get("X-Request-ID")
        assert rid
        # Generated values are 32-char hex (uuid4().hex).
        assert len(rid) >= 16


def test_request_id_propagated_from_header():
    from app.main import app

    incoming = "trace-abc-123"
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": incoming})
        assert response.headers.get("X-Request-ID") == incoming


def test_request_id_each_request_unique_when_missing():
    from app.main import app

    with TestClient(app) as client:
        rid1 = client.get("/health").headers.get("X-Request-ID")
        rid2 = client.get("/health").headers.get("X-Request-ID")

    assert rid1 and rid2
    assert rid1 != rid2


# ---------------------------------------------------------------------------
# /readyz
# ---------------------------------------------------------------------------
def test_readyz_returns_app_field_on_success():
    from app.main import readyz

    result = readyz()
    assert result["status"] == "ready"
    assert result["database"] == "ok"
    assert result["app"] == "IXAI Agent"


def test_readyz_returns_app_field_on_failure(monkeypatch):
    from app import main

    class _BoomEngine:
        def connect(self):
            raise RuntimeError("simulated db outage")

    monkeypatch.setattr(main, "engine", _BoomEngine())
    response = main.readyz()
    assert response.status_code == 503
    assert b'"app"' in response.body
    assert b'"IXAI Agent"' in response.body


def test_readyz_via_http_client_carries_request_id():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID")


# ---------------------------------------------------------------------------
# Latency middleware
# ---------------------------------------------------------------------------
def test_latency_middleware_does_not_crash_on_handler_error(caplog):
    """Even when a route raises, the latency log must still be emitted and
    no exception must propagate out of the middleware chain.

    Note: Starlette's outer error handler produces the 500 response without
    re-entering our middleware stack, so X-Request-ID is not guaranteed on
    the response body of an exception path. We assert the things we actually
    care about: response delivered, latency log emitted, no crash."""
    from app.main import app

    @app.get("/__v1c_test_raise")
    def _raise_route():
        raise RuntimeError("intentional test failure")

    try:
        caplog.set_level(logging.INFO, logger="app.core.observability")
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/__v1c_test_raise")
            assert response.status_code == 500

        # Latency middleware must have logged the request despite the handler error.
        latency_events = [
            record
            for record in caplog.records
            if record.name == "app.core.observability"
            and record.getMessage() == "request"
            and getattr(record, "path", "") == "/__v1c_test_raise"
        ]
        assert latency_events, "expected a latency log even when the handler raised"
        # The logged status_code should reflect the failure.
        assert latency_events[-1].status_code in {500, 502, 503}
    finally:
        # Best-effort: remove the temporary route so suite stays clean.
        app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != "/__v1c_test_raise"]


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------
def test_configure_logging_idempotent():
    from app.core.observability import configure_logging

    configure_logging()
    root = logging.getLogger()
    managed = [h for h in root.handlers if getattr(h, "_ixai_managed", False)]
    count_first = len(managed)

    configure_logging()
    managed_again = [h for h in root.handlers if getattr(h, "_ixai_managed", False)]
    assert len(managed_again) == count_first
    assert len(managed_again) >= 1


def test_request_context_filter_attaches_request_id():
    from app.core.observability import RequestContextFilter

    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    assert RequestContextFilter().filter(record) is True
    assert hasattr(record, "request_id")
    assert isinstance(record.request_id, str)


# ---------------------------------------------------------------------------
# Json formatter does not crash on weird payloads
# ---------------------------------------------------------------------------
def test_json_formatter_renders_extra_fields():
    from app.core.observability import _JsonFormatter

    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="request", args=(), exc_info=None,
    )
    # Simulate `extra={...}` having added attributes.
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.latency_ms = 1.23
    record.request_id = "abc"

    output = _JsonFormatter().format(record)
    assert '"method"' in output
    assert '"latency_ms"' in output
    assert '"GET"' in output
    assert '"request_id"' in output


# ---------------------------------------------------------------------------
# Privacy contract: latency log must not include auth headers / cookies.
# ---------------------------------------------------------------------------
def test_latency_log_does_not_capture_authorization(caplog):
    from app.main import app

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        client.get("/health", headers={"Authorization": "Bearer secret-token-abc"})

    combined = "\n".join(record.getMessage() + str(getattr(record, "__dict__", {})) for record in caplog.records)
    assert "secret-token-abc" not in combined
    assert "Bearer" not in combined