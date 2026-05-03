from __future__ import annotations

from typing import Any

import requests

from .base import MarketDataProvider, MarketPriceResult, utc_now_iso


class BinanceProvider(MarketDataProvider):
    BASE_URL = "https://api.binance.com/api/v3/ticker/price"

    def get_price(self, symbol: str = "BTCUSDT") -> MarketPriceResult:
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return self._error_result("", "Symbol is required")

        try:
            response = requests.get(
                self.BASE_URL,
                params={"symbol": normalized_symbol},
                timeout=8,
            )
            response.raise_for_status()

            data = response.json()
            price = self._clean_price(data.get("price"))
            if price is None:
                return self._error_result(
                    normalized_symbol,
                    f"Binance returned no usable price for symbol: {normalized_symbol}",
                )

            return MarketPriceResult(
                symbol=normalized_symbol,
                price=price,
                source="binance",
                updated_at=utc_now_iso(),
                error=None,
            )
        except Exception as exc:
            return self._error_result(
                normalized_symbol,
                f"Binance price fetch failed: {exc}",
            )

    def _error_result(self, symbol: str, error: str) -> MarketPriceResult:
        return MarketPriceResult(
            symbol=symbol,
            price=None,
            source="binance",
            updated_at=utc_now_iso(),
            error=error,
        )

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper()

    def _clean_price(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            price = float(value)
        except (TypeError, ValueError):
            return None

        if price != price or price <= 0:
            return None

        return price
