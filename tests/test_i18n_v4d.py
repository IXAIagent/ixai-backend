"""v4D: backend locale resolver tests."""
from __future__ import annotations

import pytest

from app.core.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    narrative_locale,
    resolve_locale,
)


@pytest.mark.parametrize(
    "header_value,expected",
    [
        ("zh-TW", "zh-TW"),
        ("en", "en"),
        ("ja", "ja"),
        ("ko", "ko"),
        ("zh-CN", "zh-CN"),
        ("zh-tw", "zh-TW"),  # case-insensitive
        ("EN", "en"),
        ("zh", "zh-TW"),  # primary language fallback
        ("en-US", "en"),
        ("fr", "en"),  # unsupported -> default
        ("", "en"),
        (None, "en"),
        ("klingon", "en"),
    ],
)
def test_resolve_locale_x_ixai_header(header_value, expected):
    assert resolve_locale(x_ixai_locale=header_value) == expected


def test_resolve_locale_accept_language_with_quality_factors():
    accept = "zh-TW;q=0.9,en;q=0.8"
    assert resolve_locale(accept_language=accept) == "zh-TW"


def test_resolve_locale_x_ixai_takes_precedence():
    assert (
        resolve_locale(x_ixai_locale="ja", accept_language="zh-TW")
        == "ja"
    )


def test_resolve_locale_unsupported_x_ixai_falls_through_to_accept_language():
    assert (
        resolve_locale(x_ixai_locale="klingon", accept_language="ko")
        == "ko"
    )


def test_resolve_locale_default_when_all_empty():
    assert resolve_locale() == DEFAULT_LOCALE


@pytest.mark.parametrize(
    "input_locale,narrative",
    [
        ("zh-TW", "zh-TW"),
        ("en", "en"),
        ("ja", "en"),
        ("ko", "en"),
        ("zh-CN", "en"),
        (None, "en"),
        ("klingon", "en"),
    ],
)
def test_narrative_locale_fallback(input_locale, narrative):
    """Officially-supported narratives today: en + zh-TW. Everything else
    must fall back to en without raising."""
    assert narrative_locale(input_locale) == narrative


def test_supported_locales_complete():
    assert "zh-TW" in SUPPORTED_LOCALES
    assert "en" in SUPPORTED_LOCALES
    assert "ja" in SUPPORTED_LOCALES
    assert "ko" in SUPPORTED_LOCALES
    assert "zh-CN" in SUPPORTED_LOCALES
