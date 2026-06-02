import logging
import os
from datetime import datetime

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

try:
    from app.api.v1.api import api_router
except ModuleNotFoundError:
    from app.api.v1.router import api_router
from app.core.config import is_development_env, settings
from app.core.database import Base, engine
from app.core.observability import (
    RequestIDMiddleware,
    RequestLatencyMiddleware,
    configure_logging,
    init_sentry,
)
import app.models.models  # noqa: F401

# Configure structured logging before any module-level loggers emit so the
# first lines have request_id / formatter applied.
configure_logging()

logger = logging.getLogger(__name__)


def should_run_create_all() -> bool:
    """Return True only in development/local. Production-like envs must use Alembic."""
    return is_development_env()


def _build_cors_origins() -> list[str]:
    """Build a safe CORS allowlist from env, with localhost only in dev."""
    defaults = []
    if is_development_env():
        defaults = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
        ]

    configured: list[str] = []

    # Production-like environments only trust the explicit env allowlist.
    raw_env_origins = os.getenv("BACKEND_CORS_ORIGINS", "")
    configured.extend(origin.strip() for origin in raw_env_origins.split(",") if origin.strip())

    # Remove wildcard because allow_credentials=True cannot be used safely with "*".
    origins = []
    for origin in [*defaults, *configured]:
        if origin and origin != "*" and origin not in origins:
            origins.append(origin)
    return origins


def _build_cors_origin_regex() -> str | None:
    if not is_development_env():
        return None
    return r"https://ixai-website-clean(?:-[a-zA-Z0-9]+)?-ixaiagents-projects\.vercel\.app"


app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Latency logging wraps CORS-and-below so we measure the full handler time.
# RequestID is added last so it executes first on each request, ensuring the
# id is in scope for every downstream layer (including latency logs).
app.add_middleware(RequestLatencyMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(SQLAlchemyTimeoutError)
async def sqlalchemy_timeout_handler(request: Request, exc: SQLAlchemyTimeoutError):
    logger.exception(
        "database connection checkout timed out",
        extra={"path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "detail": "Database is temporarily busy. Please retry shortly.",
        },
    )


@app.get("/")
def root():
    return {"status": "IXAI backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok", "app": settings.PROJECT_NAME}
    except Exception:
        logger.exception("readyz database ping failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "error",
                "app": settings.PROJECT_NAME,
            },
        )


# TEMPORARY v1.55.1 read-only production migration debug endpoint.
# This endpoint intentionally does not execute migrations. Remove after
# production 0010 verification is complete or replace with protected ops tooling.
@app.get("/admin/migration-status")
def migration_status():
    expected_revision = "0010_membership_foundation"

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())

        script = ScriptDirectory.from_config(Config("alembic.ini"))
        heads = script.get_heads()
        required_tables = {
            "accounts": "accounts" in tables,
            "account_memberships": "account_memberships" in tables,
            "users": "users" in tables,
            "subscriptions": "subscriptions" in tables,
            "entitlements": "entitlements" in tables,
        }

        return {
            "ok": current_revision == expected_revision and all(required_tables.values()),
            "currentRevision": current_revision,
            "expectedRevision": expected_revision,
            "heads": heads,
            "tables": required_tables,
            "temporary": True,
            "source": "ixai-backend",
            "checkedAt": datetime.utcnow().isoformat() + "Z",
        }
    except Exception:
        logger.exception("migration status check failed")
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "currentRevision": None,
                "expectedRevision": expected_revision,
                "tables": {},
                "temporary": True,
                "source": "ixai-backend",
                "checkedAt": datetime.utcnow().isoformat() + "Z",
                "error": "migration_status_unavailable",
            },
        )


@app.on_event("startup")
def init_db_tables():
    settings.validate_runtime_security()
    init_sentry()
    if should_run_create_all():
        logger.warning(
            "Using create_all in development/local only. Production must use Alembic."
        )
        Base.metadata.create_all(bind=engine)
    else:
        logger.warning(
            "Skipping create_all; production-like environments must use Alembic migrations."
        )


app.include_router(api_router, prefix="/api/v1")
