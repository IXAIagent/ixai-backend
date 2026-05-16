from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

database_url = settings.resolved_database_url

engine_kwargs = {}

if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": max(1, int(settings.DB_POOL_SIZE or 10)),
            "max_overflow": max(0, int(settings.DB_MAX_OVERFLOW or 20)),
            "pool_timeout": max(1, int(settings.DB_POOL_TIMEOUT or 30)),
            "pool_recycle": max(1, int(settings.DB_POOL_RECYCLE or 1800)),
            "pool_pre_ping": bool(settings.DB_POOL_PRE_PING),
            "pool_use_lifo": True,
        }
    )

engine = create_engine(database_url, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
