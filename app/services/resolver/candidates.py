from __future__ import annotations

from app.services.normalization import (
    detect_currency,
    detect_market,
    normalize_crypto_symbol,
    normalize_stock_symbol,
)
from app.services.normalization.crypto_master import CRYPTO_ASSETS
from app.services.normalization.tw_stock_master import TW_STOCKS
from app.services.market_data.yahoo_provider import YahooFinanceProvider


def clean_query(value: str | None) -> str:
    return str(value or "").strip().upper()


def normalize_asset_type(asset_type: str | None) -> str | None:
    value = clean_query(asset_type).lower()
    if value in {"crypto", "grid", "dual"}:
        return "crypto"
    if value in {"stock", "fcn_underlying"}:
        return "stock"
    return value or None


def candidate_from_record(record: dict, confidence: float, match_type: str, source: str, asset_type: str) -> dict:
    canonical_symbol = str(record["canonical_symbol"])
    return {
        "canonical_symbol": canonical_symbol,
        "display_name": record.get("display_name"),
        "asset_type": asset_type,
        "market": record.get("market") or detect_market(canonical_symbol),
        "currency": record.get("currency") or detect_currency(canonical_symbol),
        "confidence": confidence,
        "match_type": match_type,
        "source": source,
    }


def score_stock_record(query: str, record: dict) -> tuple[float, str] | None:
    canonical = clean_query(record.get("canonical_symbol"))
    display_name = clean_query(record.get("display_name"))
    aliases = [clean_query(alias) for alias in record.get("aliases", [])]

    if query == canonical:
        return 0.99, "canonical"
    if query in aliases:
        return 0.98, "alias"
    if query == display_name:
        return 0.95, "display_name"
    if display_name.startswith(query) or any(alias.startswith(query) for alias in aliases):
        return 0.8, "partial"
    if query in display_name or any(query in alias for alias in aliases):
        return 0.6, "partial"
    return None


def score_crypto_record(query: str, record: dict) -> tuple[float, str] | None:
    canonical = clean_query(record.get("canonical_symbol"))
    base = clean_query(record.get("base_symbol"))
    display_name = clean_query(record.get("display_name"))
    aliases = [clean_query(alias) for alias in record.get("aliases", [])]

    if query == canonical:
        return 0.99, "canonical"
    if query == base or query in aliases:
        return 0.98, "alias"
    if query == display_name:
        return 0.95, "display_name"
    if display_name.startswith(query) or any(alias.startswith(query) for alias in aliases):
        return 0.8, "partial"
    if query in display_name or any(query in alias for alias in aliases):
        return 0.6, "partial"
    return None


def stock_candidates(query: str) -> list[dict]:
    normalized_query = clean_query(query)
    candidates = []
    for record in TW_STOCKS:
        score = score_stock_record(normalized_query, record)
        if score:
            confidence, match_type = score
            candidates.append(
                candidate_from_record(record, confidence, match_type, "tw_stock_master", "stock")
            )
    return dedupe_candidates(candidates)


def crypto_candidates(query: str) -> list[dict]:
    normalized_query = clean_query(query)
    candidates = []
    for record in CRYPTO_ASSETS:
        score = score_crypto_record(normalized_query, record)
        if score:
            confidence, match_type = score
            candidates.append(
                candidate_from_record(record, confidence, match_type, "crypto_master", "crypto")
            )
    return dedupe_candidates(candidates)


def yahoo_search_stock_candidates(query: str) -> list[dict]:
    normalized_query = clean_query(query)
    if not normalized_query:
        return []

    provider = YahooFinanceProvider()
    quotes = provider.search(query)
    candidates: list[dict] = []

    for quote in quotes:
        symbol = clean_query(quote.get("symbol"))
        quote_type = clean_query(quote.get("quoteType"))
        if not symbol or quote_type not in {"EQUITY", "ETF"}:
            continue

        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            market = "TWSE"
            currency = "TWD"
            confidence = 0.82
        elif "." not in symbol:
            market = "US"
            currency = "USD"
            confidence = 0.72
        else:
            continue

        display_name = (
            str(quote.get("shortname") or quote.get("longname") or symbol)
            .strip()
        )
        canonical_symbol = normalize_stock_symbol(symbol)
        base_symbol = canonical_symbol.split(".", 1)[0]
        is_tw_common_stock = base_symbol.isdigit() and len(base_symbol) == 4
        exact_name_match = clean_query(display_name) == normalized_query

        if is_tw_common_stock and exact_name_match:
            confidence = 0.85
        elif is_tw_common_stock:
            confidence = 0.78
        elif exact_name_match:
            confidence = 0.72
        else:
            confidence = 0.62

        candidates.append(
            {
                "canonical_symbol": canonical_symbol,
                "display_name": display_name or canonical_symbol,
                "asset_type": "stock",
                "market": market,
                "currency": currency,
                "confidence": confidence,
                "match_type": "fallback",
                "source": "yahoo_search",
            }
        )

    return dedupe_candidates(candidates)


def fallback_candidate(query: str, asset_type: str | None) -> dict | None:
    normalized_type = normalize_asset_type(asset_type)
    normalized_query = clean_query(query)
    if not normalized_query:
        return None

    if normalized_type == "crypto":
        canonical_symbol = normalize_crypto_symbol(normalized_query)
        return {
            "canonical_symbol": canonical_symbol,
            "display_name": canonical_symbol.removesuffix("USDT"),
            "asset_type": "crypto",
            "market": detect_market(canonical_symbol),
            "currency": detect_currency(canonical_symbol),
            "confidence": 0.65,
            "match_type": "fallback",
            "source": "normalization",
        }

    canonical_symbol = normalize_stock_symbol(normalized_query)
    if canonical_symbol == normalized_query and not canonical_symbol.endswith(".TW"):
        confidence = 0.5
    else:
        confidence = 0.75

    return {
        "canonical_symbol": canonical_symbol,
        "display_name": canonical_symbol,
        "asset_type": "stock",
        "market": detect_market(canonical_symbol),
        "currency": detect_currency(canonical_symbol),
        "confidence": confidence,
        "match_type": "fallback",
        "source": "normalization",
    }


def dedupe_candidates(candidates: list[dict]) -> list[dict]:
    best_by_symbol: dict[str, dict] = {}
    for candidate in candidates:
        symbol = str(candidate.get("canonical_symbol") or "")
        if not symbol:
            continue
        existing = best_by_symbol.get(symbol)
        if not existing or float(candidate.get("confidence", 0)) > float(existing.get("confidence", 0)):
            best_by_symbol[symbol] = candidate

    return sorted(
        best_by_symbol.values(),
        key=lambda item: float(item.get("confidence", 0)),
        reverse=True,
    )
