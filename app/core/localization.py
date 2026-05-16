"""v4.9B: hybrid localization policy on the backend.

Mirrors the frontend protected-term registry. Today's behaviour is mostly
identity (backend engines already emit locale-aware copy through
``narrative_locale()``), but this module is the single seam that:

- Owns the canonical list of protected financial terms.
- Provides ``localize_financial_narrative()`` to compress + sanitize copy
  emitted by engines before it reaches the wire.
- Provides ``preserve_protected_terms()`` as a future hook for any LLM
  translator that needs to know which substrings to leave untouched.

Compliance: every output runs through ``compliance_filter.sanitize_text``
so the forbidden trading vocabulary cannot leak.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.core.i18n import narrative_locale
from app.services.intelligence.compliance import compliance_filter


PROTECTED_FINANCIAL_TERMS: tuple[str, ...] = (
    # Structured product terms
    "FCN",
    "KI",
    "KO",
    "Worst-of",
    "worst-of",
    # Regimes / scoring concepts kept in English even in zh narratives
    "AI Momentum",
    "Risk-On",
    "Risk-Off",
    "RISK_ON",
    "RISK_OFF",
    "AI_MOMENTUM",
    "CRYPTO_SPECULATIVE",
    "DEFENSIVE",
    "HIGH_VOLATILITY",
    # Crypto
    "BTC",
    "ETH",
    "BTCUSDT",
    "ETHUSDT",
    "USDT",
    "USDC",
    # Common tickers used by IXAI engines
    "NVDA",
    "NVIDIA",
    "AAPL",
    "MSFT",
    "TSM",
    "TSMC",
    "AVGO",
    "AMD",
    "AMZN",
    "GOOGL",
    "GOOG",
    "META",
    "TSLA",
    "PLTR",
    "MAG7",
    "Mag 7",
)


_PROTECTED_LOOKUP = {term.lower() for term in PROTECTED_FINANCIAL_TERMS}


def is_protected_term(candidate: str) -> bool:
    """True iff ``candidate`` is registered as a protected financial term."""
    return bool(candidate) and candidate.lower() in _PROTECTED_LOOKUP


def preserve_protected_terms(text: str) -> str:
    """Identity passthrough — documents intent + gives a hook for future
    LLM translators that need to mask protected runs before translation."""
    return text or ""


_TOKEN_SPLIT = re.compile(r"(\s+|[,.;:!?()\[\]{}「」、，。；])")


def tokenise_protected_runs(text: str) -> list[tuple[str, bool]]:
    """Tokenise ``text`` and flag each non-empty token's protected status."""
    if not text:
        return []
    tokens = _TOKEN_SPLIT.split(text)
    output: list[tuple[str, bool]] = []
    for token in tokens:
        if not token:
            continue
        output.append((token, is_protected_term(token.strip())))
    return output


def localize_financial_narrative(
    text: str | None,
    locale: str | None,
    *,
    max_length: int = 160,
) -> str:
    """Render an engine narrative for the user.

    Today's behaviour:
      - Always run through ``compliance_filter.sanitize_text`` as a final
        safety net against forbidden trading wording.
      - Truncate to ``max_length`` (>= 40, ellipsis applied) so the UI
        stays scan-friendly.
      - Locale parameter is the single seam for a future LLM translator;
        backend narratives already arrive locale-aware via
        ``narrative_locale()``.
    """
    if not text:
        return ""
    _ = narrative_locale(locale)  # validate + future hook
    limit = max(40, int(max_length or 160))
    sanitised = compliance_filter.sanitize_text(text, max_length=limit)
    return sanitised


def localize_list(
    items: Iterable[str] | None,
    locale: str | None,
    *,
    max_length: int = 120,
) -> list[str]:
    """Convenience wrapper for sanitising every string in a list."""
    if not items:
        return []
    return [
        localize_financial_narrative(item, locale, max_length=max_length)
        for item in items
        if isinstance(item, str) and item.strip()
    ]
