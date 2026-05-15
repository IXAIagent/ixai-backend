"""Shared pytest setup for the IXAI backend test suite."""
import os

# Default test environment to "development" so the app's startup security
# validation does not require a production SECRET_KEY. Individual tests may
# override via monkeypatch.setenv("APP_ENV", "production").
os.environ.setdefault("APP_ENV", "development")
