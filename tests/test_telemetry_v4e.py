"""v4E: telemetry helper tests."""
from __future__ import annotations

import logging

import pytest

from app.core.telemetry import TimingContext, record_event, timed


def test_record_event_does_not_raise():
    record_event("smoke", portfolio_id="pf-1", status="ok")


def test_record_event_strips_sensitive_keys(caplog):
    caplog.set_level(logging.INFO, logger="app.core.telemetry")
    record_event("smoke", portfolio_id="pf-1", token="should-not-leak", password="x")
    messages = "\n".join(rec.getMessage() + str(rec.__dict__) for rec in caplog.records)
    assert "should-not-leak" not in messages
    # password key was stripped before logger.extra
    assert "x" not in messages or "telemetry_password" not in messages


def test_timed_decorator_emits_success(caplog):
    caplog.set_level(logging.INFO, logger="app.core.telemetry")

    @timed("unit_under_test")
    def add(a, b):
        return a + b

    assert add(2, 3) == 5
    timing_records = [
        rec for rec in caplog.records if getattr(rec, "telemetry_event", None) == "timing"
    ]
    assert len(timing_records) == 1
    assert timing_records[0].telemetry_status == "ok"
    assert getattr(timing_records[0], "telemetry_latency_ms", -1) >= 0


def test_timed_decorator_records_error_and_reraises(caplog):
    caplog.set_level(logging.INFO, logger="app.core.telemetry")

    @timed("boom")
    def explode():
        raise ValueError("kaboom")

    with pytest.raises(ValueError):
        explode()

    timing_records = [
        rec for rec in caplog.records if getattr(rec, "telemetry_event", None) == "timing"
    ]
    assert len(timing_records) == 1
    assert timing_records[0].telemetry_status == "error"
    assert timing_records[0].telemetry_error_type == "ValueError"


def test_timing_context_manager_emits_on_exit(caplog):
    caplog.set_level(logging.INFO, logger="app.core.telemetry")
    with TimingContext("ctx_block", portfolio_id="pf-1"):
        pass
    records = [
        rec for rec in caplog.records if getattr(rec, "telemetry_event", None) == "timing"
    ]
    assert any(r.telemetry_name == "ctx_block" for r in records)


def test_timing_context_records_error(caplog):
    caplog.set_level(logging.INFO, logger="app.core.telemetry")
    with pytest.raises(RuntimeError):
        with TimingContext("ctx_err"):
            raise RuntimeError("boom")
    records = [
        rec for rec in caplog.records if getattr(rec, "telemetry_event", None) == "timing"
    ]
    err = [r for r in records if r.telemetry_name == "ctx_err"]
    assert err and err[-1].telemetry_status == "error"
