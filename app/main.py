import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

try:
    from app.api.v1.api import api_router
except ModuleNotFoundError:
    from app.api.v1.router import api_router
from app.core.config import is_development_env, settings
from app.core.database import Base, engine
import app.models.models  # noqa: F401

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
        return {"status": "ready", "database": "ok"}
    except Exception:
        logger.exception("readyz database ping failed")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "error"},
        )


@app.on_event("startup")
def init_db_tables():
    settings.validate_runtime_security()
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
