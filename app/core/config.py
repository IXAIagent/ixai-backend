import os

from pydantic_settings import BaseSettings

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_DEV_SECRET_KEY = "ixai-local-dev-secret-key-change-before-production"
DEVELOPMENT_ENVS = {"development", "dev", "local"}
PRODUCTION_ENVS = {"production", "prod"}
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
    env = runtime_environment()
    return env in PRODUCTION_ENVS or env == ""


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url[len("postgres://"):]
    return database_url

class Settings(BaseSettings):
    PROJECT_NAME: str = "IXAI Agent"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = DEFAULT_SQLITE_DATABASE_URL

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Telegram push notification settings
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False

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

        if is_production_env() or self.ENVIRONMENT.lower() in {"production", "prod", "staging"}:
            raise RuntimeError("SECRET_KEY must be set in production.")

        return _DEV_SECRET_KEY

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
