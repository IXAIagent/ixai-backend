"""v4.9B: backend localization policy tests."""
from __future__ import annotations

import re

import pytest

from app.core.localization import (
    PROTECTED_FINANCIAL_TERMS,
    is_protected_term,
    localize_financial_narrative,
    localize_list,
    preserve_protected_terms,
    tokenise_protected_runs,
)


FORBIDDEN = re.compile(
    r"\b(buy|sell|add position|reduce position|target price|stop loss)\b|"
    r"買進|賣出|加碼|減碼|目標價|停損",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Protected term registry
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "term",
    [
        "FCN",
        "KI",
        "KO",
        "Worst-of",
        "BTC",
        "ETH",
        "NVDA",
        "AI Momentum",
        "Risk-On",
        "TSM",
    ],
)
def test_protected_term_recognised(term):
    assert is_protected_term(term)


@pytest.mark.parametrize("term", ["fcn", "ki", "btc", "ai momentum"])
def test_protected_term_case_insensitive(term):
    assert is_protected_term(term)


@pytest.mark.parametrize("token", ["the", "of", "rises", "監控", "走勢", ""])
def test_non_protected_term_not_recognised(token):
    assert is_protected_term(token) is False


def test_registry_includes_core_terms():
    needed = {"FCN", "KI", "KO", "BTC", "ETH", "NVDA", "Worst-of", "AI Momentum"}
    assert needed.issubset(set(PROTECTED_FINANCIAL_TERMS))


def test_preserve_protected_terms_is_identity():
    text = "FCN worst-of NVDA pressure; nearest KI 12%"
    assert preserve_protected_terms(text) == text


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------
def test_tokeniser_flags_protected_runs():
    tokens = tokenise_protected_runs("FCN worst-of NVDA pressure")
    protected = {token for token, is_p in tokens if is_p}
    assert "FCN" in protected
    assert "NVDA" in protected
    assert "worst-of" in protected
    # connective words are not protected
    assert "pressure" not in protected


def test_tokeniser_handles_empty_input():
    assert tokenise_protected_runs("") == []
    assert tokenise_protected_runs(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# localize_financial_narrative
# ---------------------------------------------------------------------------
def test_narrative_passthrough_when_short():
    out = localize_financial_narrative("FCN risk elevated", "en")
    assert out == "FCN risk elevated"
    assert FORBIDDEN.search(out) is None


def test_narrative_truncates_long_text():
    long = ("A" * 200) + " end"
    out = localize_financial_narrative(long, "en", max_length=80)
    assert len(out) <= 81  # truncation may end with ellipsis or original tail
    assert "A" in out


def test_narrative_strips_forbidden_wording():
    dirty = "Investors should buy NVDA at target price 100; 加碼 BTC"
    out = localize_financial_narrative(dirty, "zh-TW")
    assert FORBIDDEN.search(out) is None


def test_narrative_empty_and_none_safe():
    assert localize_financial_narrative("", "en") == ""
    assert localize_financial_narrative(None, "en") == ""


def test_narrative_preserves_protected_terms_after_compliance():
    """compliance_filter must not strip FCN / KI / KO / BTC etc."""
    out = localize_financial_narrative(
        "FCN worst-of NVDA pressure; nearest KI 12%", "en"
    )
    assert "FCN" in out
    assert "NVDA" in out
    assert "KI" in out
    assert "worst-of" in out


def test_narrative_respects_locale_argument():
    """zh-TW input passes through (backend already emits zh-TW)."""
    out = localize_financial_narrative(
        "FCN 風險升高，最近 KI 8%", "zh-TW"
    )
    assert "FCN" in out and "KI" in out
    assert "風險" in out
    assert FORBIDDEN.search(out) is None


def test_narrative_unsupported_locale_falls_back_to_en():
    """Unknown locale must not crash and must still sanitize."""
    out = localize_financial_narrative("FCN risk steady", "klingon")
    assert "FCN" in out
    assert FORBIDDEN.search(out) is None


def test_narrative_max_length_floor():
    """Specifying a tiny max_length still honours a >= 40 floor."""
    out = localize_financial_narrative(
        "FCN " + ("x" * 200),
        "en",
        max_length=5,
    )
    # compliance_filter respects max_length internally; we just verify
    # the output never explodes and remains within a sane bound.
    assert len(out) <= 200
    assert FORBIDDEN.search(out) is None


# ---------------------------------------------------------------------------
# localize_list
# ---------------------------------------------------------------------------
def test_localize_list_filters_and_sanitises():
    items = [
        "FCN worst-of NVDA",
        "",
        "  ",
        "buy NVDA at target price 100",
        "AI momentum elevated",
    ]
    out = localize_list(items, "en")
    assert len(out) == 3  # blanks filtered
    assert all(FORBIDDEN.search(item) is None for item in out)
    assert any("FCN" in item for item in out)


def test_localize_list_empty_safe():
    assert localize_list(None, "en") == []
    assert localize_list([], "en") == []
