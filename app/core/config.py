import os
import secrets

from pydantic_settings import BaseSettings

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_DEV_SECRET_KEY = secrets.token_urlsafe(32)

class Settings(BaseSettings):
    PROJECT_NAME: str = "IXAI Agent"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite:///./ixai.db"

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

        if self.ENVIRONMENT.lower() in {"production", "prod", "staging"}:
            raise RuntimeError("SECRET_KEY must be set in production.")

        return _DEV_SECRET_KEY

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
