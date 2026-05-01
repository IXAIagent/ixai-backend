from __future__ import annotations

from typing import Literal

from app.services.market_data.binance_provider import BinanceProvider
from app.services.market_data.yahoo_provider import YahooProvider

SymbolType = Literal["crypto", "stock"]


class MarketDataService:
    DEFAULT_CRYPTO_QUOTE = "USDT"

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
        yahoo_provider: YahooProvider | None = None,
    ) -> None:
        self.binance_provider = binance_provider or BinanceProvider()
        self.yahoo_provider = yahoo_provider or YahooProvider()

    def get_price(self, symbol: str) -> float:
        normalized_symbol = self._normalize_symbol(symbol)
        symbol_type = self.detect_symbol_type(normalized_symbol)

        if symbol_type == "crypto":
            return self.binance_provider.get_price(
                self._to_binance_symbol(normalized_symbol)
            )

        return self.yahoo_provider.get_price(normalized_symbol)

    def detect_symbol_type(self, symbol: str) -> SymbolType:
        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol in self.CRYPTO_SYMBOLS:
            return "crypto"

        if normalized_symbol.endswith(self.DEFAULT_CRYPTO_QUOTE):
            base_symbol = normalized_symbol[: -len(self.DEFAULT_CRYPTO_QUOTE)]
            if base_symbol in self.CRYPTO_SYMBOLS:
                return "crypto"

        if normalized_symbol.endswith("-USD"):
            base_symbol = normalized_symbol.removesuffix("-USD")
            if base_symbol in self.CRYPTO_SYMBOLS:
                return "crypto"

        return "stock"

    def _to_binance_symbol(self, symbol: str) -> str:
        normalized_symbol = self._normalize_symbol(symbol)

        if normalized_symbol.endswith(self.DEFAULT_CRYPTO_QUOTE):
            return normalized_symbol

        if normalized_symbol.endswith("-USD"):
            base_symbol = normalized_symbol.removesuffix("-USD")
            return f"{base_symbol}{self.DEFAULT_CRYPTO_QUOTE}"

        return f"{normalized_symbol}{self.DEFAULT_CRYPTO_QUOTE}"

    def _normalize_symbol(self, symbol: str) -> str:
        if not symbol or not symbol.strip():
            raise ValueError("Symbol is required")

        return symbol.strip().upper()
