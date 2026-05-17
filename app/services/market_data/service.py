from __future__ import annotations

import logging
import time
from typing import Literal

logger = logging.getLogger(__name__)

try:
    from cachetools import TTLCache
except ImportError:  # pragma: no cover - used only before dependencies are installed.
    class TTLCache(dict):
        def __init__(self, maxsize: int, ttl: int):
            super().__init__()
            self.maxsize = maxsize
            self.ttl = ttl
            self._expires: dict[object, float] = {}

        def __contains__(self, key: object) -> bool:
            expires_at = self._expires.get(key)
            if expires_at is None or expires_at <= time.monotonic():
                self.pop(key, None)
                self._expires.pop(key, None)
                return False
            return super().__contains__(key)

        def __getitem__(self, key):
            if key not in self:
                raise KeyError(key)
            return super().__getitem__(key)

        def __setitem__(self, key, value) -> None:
            if len(self) >= self.maxsize:
                oldest_key = next(iter(self))
                self.pop(oldest_key, None)
                self._expires.pop(oldest_key, None)
            self._expires[key] = time.monotonic() + self.ttl
            super().__setitem__(key, value)

from app.services.market_data.base import MarketPriceResult, utc_now_iso
from app.services.market_data.binance_provider import BinanceProvider
from app.services.market_data.yahoo_provider import YahooFinanceProvider
from app.services.normalization import (
    get_crypto_yahoo_fallback_symbol,
    normalize_crypto_symbol,
    normalize_stock_symbol,
)
from app.services.crypto_subtypes import get_crypto_base_type

SymbolType = Literal["crypto", "stock"]


class MarketDataService:
    DEFAULT_CRYPTO_QUOTE = "USDT"
    _price_cache = TTLCache(maxsize=500, ttl=60)

    CRYPTO_ASSET_TYPES = {"crypto", "spot", "grid", "dual", "stablecoin_earn"}
    CRYPTO_SYMBOLS = {
        "BTC",
        "ETH",
        "BNB",
        "SOL",
        "XRP",
        "ADA",
        "DOGE",
        "AVAX",
        "DOT",
        "TRX",
        "LINK",
        "MATIC",
        "LTC",
        "BCH",
        "UNI",
        "ATOM",
        "ETC",
        "XLM",
        "FIL",
        "APT",
        "ARB",
        "OP",
        "SUI",
        "NEAR",
        "INJ",
        "SEI",
        "AAVE",
        "PEPE",
        "SHIB",
    }

    def __init__(
        self,
        binance_provider: BinanceProvider | None = None,
        yahoo_provider: YahooFinanceProvider | None = None,
    ) -> None:
        self.binance_provider = binance_provider or BinanceProvider()
        self.yahoo_provider = yahoo_provider or YahooFinanceProvider()

    def get_price(
        self,
        symbol: str,
        asset_type: str | None = None,
    ) -> MarketPriceResult:
        normalized_symbol = self._normalize_symbol(symbol, asset_type=asset_type)
        if not normalized_symbol:
            return self._manual_result("", "Symbol is required")

        cache_key = self._cache_key(normalized_symbol, asset_type)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        if self._should_use_binance(normalized_symbol, asset_type):
            provider_symbol = self._to_binance_symbol(normalized_symbol)
            provider_result = self._safe_provider_get(
                self.binance_provider,
                provider_symbol,
            )
            if provider_result.price is not None:
                return self._cache_result(cache_key, provider_result)

            yahoo_symbol = get_crypto_yahoo_fallback_symbol(provider_symbol)
            if yahoo_symbol:
                yahoo_result = self._safe_provider_get(
                    self.yahoo_provider,
                    yahoo_symbol,
                )
                if yahoo_result.price is not None:
                    return self._cache_result(cache_key, yahoo_result)

            return self._with_manual_fallback(provider_result, provider_symbol)

        result = self._with_manual_fallback(
            provider_result=self._safe_provider_get(
                self.yahoo_provider,
                normalized_symbol,
            ),
            symbol=normalized_symbol,
        )
        return self._cache_result(cache_key, result)

    def get_price_value(
        self,
        symbol: str,
        asset_type: str | None = None,
    ) -> float | None:
        return self.get_price(symbol, asset_type=asset_type).price

    def detect_symbol_type(
        self,
        symbol: str,
        asset_type: str | None = None,
    ) -> SymbolType:
        normalized_symbol = self._normalize_symbol(symbol, asset_type=asset_type)
        return "crypto" if self._should_use_binance(normalized_symbol, asset_type) else "stock"

    def _should_use_binance(self, symbol: str, asset_type: str | None) -> bool:
        normalized_asset_type = get_crypto_base_type(asset_type) if str(asset_type or "").strip() else ""
        if normalized_asset_type in self.CRYPTO_ASSET_TYPES:
            return True

        if symbol in self.CRYPTO_SYMBOLS:
            return True

        if symbol.endswith(self.DEFAULT_CRYPTO_QUOTE):
            base_symbol = symbol[: -len(self.DEFAULT_CRYPTO_QUOTE)]
            return self._looks_like_crypto_base(base_symbol)

        if symbol.endswith("-USD"):
            base_symbol = symbol.removesuffix("-USD")
            return self._looks_like_crypto_base(base_symbol)

        return False

    def _looks_like_crypto_base(self, base_symbol: str) -> bool:
        return (
            base_symbol in self.CRYPTO_SYMBOLS
            or (2 <= len(base_symbol) <= 10 and base_symbol.isalnum())
        )

    def _to_binance_symbol(self, symbol: str) -> str:
        return normalize_crypto_symbol(symbol)

    def _safe_provider_get(self, provider, symbol: str) -> MarketPriceResult:
        provider_name = self._provider_source(provider)
        try:
            result = provider.get_price(symbol)
            if isinstance(result, MarketPriceResult):
                # Surface upstream-reported errors (provider already swallowed them).
                if result.price is None and result.error:
                    logger.warning(
                        "market provider returned no price",
                        extra={
                            "provider": provider_name,
                            "operation": "get_price",
                            "symbol": symbol,
                            "error_type": "no_price",
                        },
                    )
                return result

            price = float(result)
            return MarketPriceResult(
                symbol=symbol,
                price=price,
                source=provider_name,
                updated_at=utc_now_iso(),
                error=None,
            )
        except Exception as exc:
            logger.exception(
                "market provider failure",
                extra={
                    "provider": provider_name,
                    "operation": "get_price",
                    "symbol": symbol,
                    "error_type": type(exc).__name__,
                },
            )
            return MarketPriceResult(
                symbol=symbol,
                price=None,
                source=provider_name,
                updated_at=utc_now_iso(),
                error=str(exc),
            )

    def _provider_source(self, provider) -> str:
        name = getattr(provider, "source", None)
        if name:
            return str(name)

        provider_name = provider.__class__.__name__.lower()
        if "binance" in provider_name:
            return "binance"
        if "yahoo" in provider_name:
            return "yahoo"

        return provider_name

    def _with_manual_fallback(
        self,
        provider_result: MarketPriceResult,
        symbol: str,
    ) -> MarketPriceResult:
        if provider_result.price is not None:
            return provider_result

        source = provider_result.source or "market data"
        error = provider_result.error or f"{source} price unavailable"
        return self._manual_result(symbol, error)

    def _manual_result(self, symbol: str, error: str) -> MarketPriceResult:
        return MarketPriceResult(
            symbol=symbol,
            price=None,
            source="manual",
            updated_at=utc_now_iso(),
            error=error,
        )

    def _normalize_symbol(self, symbol: str, asset_type: str | None = None) -> str:
        normalized_asset_type = get_crypto_base_type(asset_type) if str(asset_type or "").strip() else ""
        if normalized_asset_type in self.CRYPTO_ASSET_TYPES:
            return normalize_crypto_symbol(symbol)
        return normalize_stock_symbol(symbol)

    def _cache_key(self, normalized_symbol: str, asset_type: str | None) -> tuple[str, str]:
        return (
            str(normalized_symbol or "").strip().upper(),
            get_crypto_base_type(asset_type),
        )

    def _cache_result(
        self,
        cache_key: tuple[str, str],
        result: MarketPriceResult,
    ) -> MarketPriceResult:
        if result.price is None:
            return result

        try:
            if float(result.price) <= 0:
                return result
        except (TypeError, ValueError):
            return result

        self._price_cache[cache_key] = result
        return result
