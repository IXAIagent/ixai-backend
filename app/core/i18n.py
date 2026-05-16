"""v4D: backend locale resolver.

Reads the active locale from the request (header chain: `x-ixai-locale`
first, then `Accept-Language`) and exposes a `resolve_locale_header()`
helper for endpoint dependencies. Falls back to ``en`` for anything
unsupported.

Engines should accept an optional ``locale`` argument and choose between
the two officially-supported tongues today: ``en`` and ``zh-TW``. All
other recognised locales fall back to English.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import Header

SUPPORTED_LOCALES: tuple[str, ...] = ("zh-TW", "en", "ja", "ko", "zh-CN")
DEFAULT_LOCALE = "en"


def _normalise(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    # exact match
    if candidate in SUPPORTED_LOCALES:
        return candidate
    # case-insensitive exact match
    lower = candidate.lower()
    for supported in SUPPORTED_LOCALES:
        if supported.lower() == lower:
            return supported
    # language-only fallback (e.g. "zh" -> "zh-TW", "en-US" -> "en")
    primary = lower.split("-", 1)[0]
    if primary == "en":
        return "en"
    if primary == "ja":
        return "ja"
    if primary == "ko":
        return "ko"
    if primary == "zh":
        return "zh-TW"
    return None


def _parse_accept_language(raw: str | None) -> Iterable[str]:
    if not raw:
        return ()
    parts = [part.strip() for part in raw.split(",")]
    cleaned: list[str] = []
    for part in parts:
        if not part:
            continue
        # strip q-factor: "zh-TW;q=0.9" -> "zh-TW"
        cleaned.append(part.split(";", 1)[0].strip())
    return cleaned


def resolve_locale(
    *,
    x_ixai_locale: str | None = None,
    accept_language: str | None = None,
) -> str:
    """Pure resolver. Returns one of SUPPORTED_LOCALES, defaulting to ``en``."""
    candidate = _normalise(x_ixai_locale)
    if candidate:
        return candidate
    for entry in _parse_accept_language(accept_language):
        candidate = _normalise(entry)
        if candidate:
            return candidate
    return DEFAULT_LOCALE


def resolve_locale_header(
    x_ixai_locale: str | None = Header(default=None, alias="X-IXAI-Locale"),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
) -> str:
    """FastAPI dependency variant for endpoints."""
    return resolve_locale(
        x_ixai_locale=x_ixai_locale, accept_language=accept_language
    )


def narrative_locale(locale: str | None) -> str:
    """Officially-supported narrative locale. v4D ships proper text for
    ``en`` and ``zh-TW``; all other supported locales fall back to ``en``.
    """
    candidate = _normalise(locale) or DEFAULT_LOCALE
    if candidate == "zh-TW":
        return "zh-TW"
    return "en"
