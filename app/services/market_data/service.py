from __future__ import annotations

from typing import Literal

from app.services.market_data.base import MarketPriceResult, utc_now_iso
from app.services.market_data.binance_provider import BinanceProvider
from app.services.market_data.yahoo_provider import YahooFinanceProvider

SymbolType = Literal["crypto", "stock"]


class MarketDataService:
    DEFAULT_CRYPTO_QUOTE = "USDT"

    CRYPTO_ASSET_TYPES = {"crypto", "grid", "dual"}
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
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return self._manual_result("", "Symbol is required")

        if self._should_use_binance(normalized_symbol, asset_type):
            provider_symbol = self._to_binance_symbol(normalized_symbol)
            return self._with_manual_fallback(
                provider_result=self._safe_provider_get(
                    self.binance_provider,
                    provider_symbol,
                ),
                symbol=provider_symbol,
            )

        return self._with_manual_fallback(
            provider_result=self._safe_provider_get(
                self.yahoo_provider,
                normalized_symbol,
            ),
            symbol=normalized_symbol,
        )

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
        normalized_symbol = self._normalize_symbol(symbol)
        return "crypto" if self._should_use_binance(normalized_symbol, asset_type) else "stock"

    def _should_use_binance(self, symbol: str, asset_type: str | None) -> bool:
        normalized_asset_type = str(asset_type or "").strip().lower()
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
        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol.endswith(self.DEFAULT_CRYPTO_QUOTE):
            return normalized_symbol

        if normalized_symbol.endswith("-USD"):
            base_symbol = normalized_symbol.removesuffix("-USD")
            return f"{base_symbol}{self.DEFAULT_CRYPTO_QUOTE}"

        return f"{normalized_symbol}{self.DEFAULT_CRYPTO_QUOTE}"

    def _safe_provider_get(self, provider, symbol: str) -> MarketPriceResult:
        try:
            result = provider.get_price(symbol)
            if isinstance(result, MarketPriceResult):
                return result

            price = float(result)
            return MarketPriceResult(
                symbol=symbol,
                price=price,
                source=self._provider_source(provider),
                updated_at=utc_now_iso(),
                error=None,
            )
        except Exception as exc:
            return MarketPriceResult(
                symbol=symbol,
                price=None,
                source=self._provider_source(provider),
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

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper()
