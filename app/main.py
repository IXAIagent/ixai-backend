import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from app.api.v1.api import api_router
except ModuleNotFoundError:
    from app.api.v1.router import api_router
from app.core.config import settings


def _build_cors_origins() -> list[str]:
    """Build a safe CORS allowlist for local dev, Vercel frontend, and env config."""
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ixai-website-clean.vercel.app",
    ]

    configured: list[str] = []

    # Prefer settings.cors_origins when config.py provides it.
    raw_settings_origins = getattr(settings, "cors_origins", None)
    if isinstance(raw_settings_origins, list):
        configured.extend(str(origin).strip() for origin in raw_settings_origins if str(origin).strip())
    elif isinstance(raw_settings_origins, str):
        configured.extend(origin.strip() for origin in raw_settings_origins.split(",") if origin.strip())

    # Also support Render/Vercel env var directly.
    raw_env_origins = os.getenv("BACKEND_CORS_ORIGINS", "")
    configured.extend(origin.strip() for origin in raw_env_origins.split(",") if origin.strip())

    # Remove wildcard because allow_credentials=True cannot be used safely with "*".
    origins = []
    for origin in [*defaults, *configured]:
        if origin and origin != "*" and origin not in origins:
            origins.append(origin)
    return origins


app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    # Allows Vercel preview deployments for this project while keeping credentials enabled.
    allow_origin_regex=r"https://ixai-website-clean(?:-[a-zA-Z0-9]+)?-ixaiagents-projects\.vercel\.app",
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


app.include_router(api_router, prefix="/api/v1")
