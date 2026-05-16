import os
import logging

from pydantic_settings import BaseSettings

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
logger = logging.getLogger(__name__)

DEV_ONLY_SECRET_KEY = "ixai-local-dev-secret-key-change-before-production"
DEVELOPMENT_ENVS = {"development", "dev", "local"}
PRODUCTION_ENVS = {"production", "prod", "staging"}
DEFAULT_SQLITE_DATABASE_URL = "sqlite:///./ixai.db"


def runtime_environment() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).strip().lower()


def is_development_env() -> bool:
    return runtime_environment() in DEVELOPMENT_ENVS


def is_production_env() -> bool:
    return runtime_environment() in PRODUCTION_ENVS


def is_production_like_env() -> bool:
    return not is_development_env()


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://"):]
    return database_url

class Settings(BaseSettings):
    PROJECT_NAME: str = "IXAI Agent"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = ""

    DATABASE_URL: str = DEFAULT_SQLITE_DATABASE_URL

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Telegram push notification settings
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False
    NEWS_CACHE_TTL: int = 3600
    NEWS_MAX_ARTICLES_PER_SYMBOL: int = 5
    NEWS_MAX_TOTAL_ARTICLES: int = 20
    NEWS_SUMMARY_PROVIDER: str = "rule_based"
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-sonnet-4-5"
    INTELLIGENCE_AI_NARRATIVE: bool = False
    INTELLIGENCE_SCHEDULER_ENABLED: bool = False
    INTELLIGENCE_SCHEDULER_BATCH_LIMIT: int = 100
    INTELLIGENCE_SCHEDULER_INTERVAL_MINUTES: int = 60
    INTELLIGENCE_SCHEDULER_SKIP_NEWS: bool = True
    INTELLIGENCE_NEWS_MIN_INTERVAL_SECONDS: int = 3600

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True

    # Observability (v1C). All optional; absence disables Sentry without error.
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def resolved_secret_key(self) -> str:
        if self.SECRET_KEY:
            return self.SECRET_KEY

        if is_development_env():
            logger.warning("Using DEV_ONLY_SECRET_KEY fallback. This is allowed only in development/local.")
            return DEV_ONLY_SECRET_KEY

        raise RuntimeError("SECRET_KEY must be set in production-like environments.")

    def validate_runtime_security(self) -> None:
        _ = self.resolved_secret_key

    @property
    def resolved_database_url(self) -> str:
        database_url = (self.DATABASE_URL or "").strip()
        environment = (runtime_environment() or self.ENVIRONMENT or "").strip().lower()

        if environment in {"production", "prod", "staging"} and (
            not database_url or database_url == DEFAULT_SQLITE_DATABASE_URL
        ):
            raise RuntimeError("DATABASE_URL must be set in production.")

        if not database_url:
            database_url = DEFAULT_SQLITE_DATABASE_URL

        return normalize_database_url(database_url)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
