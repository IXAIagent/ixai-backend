"""Regression tests for Engineering Hardening Pack v1A.

Covers:
- should_run_create_all gating (dev vs production-like vs unset env)
- _demo_password gating (fixed in dev, random token in production-like)
- /readyz endpoint behaviour when the database ping succeeds
"""


def test_should_run_create_all_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    from app import main

    assert main.should_run_create_all() is True


def test_should_run_create_all_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app import main

    assert main.should_run_create_all() is False


def test_should_run_create_all_when_env_unset(monkeypatch):
    # Unknown environment is treated as production-like; create_all must not run.
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app import main

    assert main.should_run_create_all() is False


def test_demo_password_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    from app.api.v1.endpoints import portfolio_input

    assert portfolio_input._demo_password() == "demo"


def test_demo_password_in_production_is_random(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app.api.v1.endpoints import portfolio_input

    password = portfolio_input._demo_password()
    assert password != "demo"
    # secrets.token_urlsafe(32) returns roughly 43 characters of url-safe text.
    assert len(password) >= 20


def test_demo_password_in_production_is_not_deterministic(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app.api.v1.endpoints import portfolio_input

    assert portfolio_input._demo_password() != portfolio_input._demo_password()


def test_readyz_returns_ready_when_db_ok():
    from app.main import readyz

    # Direct function call exercises the real DB ping path without requiring
    # httpx/TestClient. v1C added an `app` field; assert the invariant subset
    # so this test does not break when readyz payload is extended.
    result = readyz()
    assert result["status"] == "ready"
    assert result["database"] == "ok"


def test_readyz_returns_503_when_db_fails(monkeypatch):
    from app import main

    class _BoomEngine:
        def connect(self):
            raise RuntimeError("simulated db outage")

    monkeypatch.setattr(main, "engine", _BoomEngine())

    response = main.readyz()
    assert response.status_code == 503
    # JSONResponse stores the rendered body as bytes; verify the failure shape.
    assert b'"not_ready"' in response.body
    assert b'"error"' in response.body


def test_health_still_returns_ok():
    from app.main import health

    assert health() == {"status": "ok"}
