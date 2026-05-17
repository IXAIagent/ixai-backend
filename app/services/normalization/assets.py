from __future__ import annotations

from app.services.normalization.crypto_master import CRYPTO_ASSETS
from app.services.normalization.tw_stock_master import TW_STOCKS
from app.services.crypto_subtypes import get_crypto_base_type

DEFAULT_CRYPTO_QUOTE = "USDT"
CRYPTO_ASSET_TYPES = {"crypto", "spot", "grid", "dual", "stablecoin_earn"}


def _clean(value: str | None) -> str:
    return str(value or "").strip().upper()


def _tw_alias_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in TW_STOCKS:
        index[_clean(item["canonical_symbol"])] = item
        for alias in item.get("aliases", []):
            index[_clean(alias)] = item
    return index


def _crypto_alias_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in CRYPTO_ASSETS:
        index[_clean(item["canonical_symbol"])] = item
        index[_clean(item["base_symbol"])] = item
        for alias in item.get("aliases", []):
            index[_clean(alias)] = item
    return index


TW_ALIAS_INDEX = _tw_alias_index()
CRYPTO_ALIAS_INDEX = _crypto_alias_index()


def normalize_stock_symbol(input: str) -> str:
    symbol = _clean(input)
    if not symbol:
        return symbol

    record = TW_ALIAS_INDEX.get(symbol)
    if record:
        return str(record["canonical_symbol"])

    if symbol.isdigit() and len(symbol) == 4:
        return f"{symbol}.TW"

    return symbol


def normalize_crypto_symbol(input: str) -> str:
    symbol = _clean(input)
    if not symbol:
        return symbol

    record = CRYPTO_ALIAS_INDEX.get(symbol)
    if record:
        return str(record["canonical_symbol"])

    if symbol.endswith("-USD"):
        return f"{symbol.removesuffix('-USD')}{DEFAULT_CRYPTO_QUOTE}"

    if symbol.endswith(DEFAULT_CRYPTO_QUOTE):
        return symbol

    return f"{symbol}{DEFAULT_CRYPTO_QUOTE}"


def normalize_asset_symbol(input: str, asset_type: str | None = None) -> str:
    normalized_type = get_crypto_base_type(asset_type) if str(asset_type or "").strip() else ""
    symbol = _clean(input)

    if normalized_type in CRYPTO_ASSET_TYPES:
        return normalize_crypto_symbol(symbol)

    if symbol in CRYPTO_ALIAS_INDEX:
        return normalize_crypto_symbol(symbol)

    return normalize_stock_symbol(symbol)


def get_asset_display_name(symbol: str, asset_type: str | None = None) -> str:
    normalized_type = get_crypto_base_type(asset_type) if str(asset_type or "").strip() else ""
    raw_symbol = _clean(symbol)

    if normalized_type in CRYPTO_ASSET_TYPES or raw_symbol in CRYPTO_ALIAS_INDEX:
        canonical = normalize_crypto_symbol(raw_symbol)
        record = CRYPTO_ALIAS_INDEX.get(canonical)
        display = str((record or {}).get("display_name") or canonical.removesuffix(DEFAULT_CRYPTO_QUOTE))
        return f"{display} {canonical}"

    canonical = normalize_stock_symbol(raw_symbol)
    record = TW_ALIAS_INDEX.get(canonical)
    if record:
        return f"{record['display_name']} {canonical}"

    return canonical


def detect_market(symbol: str) -> str:
    raw_symbol = _clean(symbol)
    if raw_symbol in CRYPTO_ALIAS_INDEX:
        return "BINANCE"

    normalized_stock = normalize_stock_symbol(raw_symbol)
    if normalized_stock.endswith(".TW"):
        return "TWSE"

    return "US"


def detect_currency(symbol: str) -> str:
    raw_symbol = _clean(symbol)
    if raw_symbol in CRYPTO_ALIAS_INDEX:
        return "USDT"

    normalized_stock = normalize_stock_symbol(raw_symbol)
    if normalized_stock.endswith(".TW"):
        return "TWD"

    return "USD"


def get_crypto_yahoo_fallback_symbol(input: str) -> str | None:
    symbol = _clean(input)
    if not symbol:
        return None

    record = CRYPTO_ALIAS_INDEX.get(symbol)
    if record:
        fallback = record.get("yahoo_fallback_symbol")
        return str(fallback) if fallback else None

    if symbol.endswith(DEFAULT_CRYPTO_QUOTE):
        base = symbol[: -len(DEFAULT_CRYPTO_QUOTE)]
        record = CRYPTO_ALIAS_INDEX.get(base)
        if record:
            fallback = record.get("yahoo_fallback_symbol")
            return str(fallback) if fallback else None

    if symbol.endswith("-USD"):
        return symbol

    return None
