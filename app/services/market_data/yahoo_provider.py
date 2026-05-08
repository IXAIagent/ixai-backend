from __future__ import annotations

from typing import Any
from urllib.parse import quote as url_quote

import requests

from .base import MarketDataProvider, MarketPriceResult, utc_now_iso

try:
    import yfinance as yf
except Exception:
    yf = None


class YahooFinanceProvider(MarketDataProvider):
    QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
    SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
    TW_AUTOCOMPLETE_URL = "https://tw.stock.yahoo.com/_td-stock/api/resource/AutocompleteService"

    def get_price(self, symbol: str) -> MarketPriceResult:
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return self._error_result("", "Symbol is required")

        errors: list[str] = []

        if yf is not None:
            price, error = self._get_price_with_yfinance(normalized_symbol)
            if price is not None:
                return MarketPriceResult(
                    symbol=normalized_symbol,
                    price=price,
                    source="yahoo",
                    updated_at=utc_now_iso(),
                    error=None,
                )
            if error:
                errors.append(error)
        else:
            errors.append("yfinance is not installed")

        price, error = self._get_price_with_quote_api(normalized_symbol)
        if price is not None:
            return MarketPriceResult(
                symbol=normalized_symbol,
                price=price,
                source="yahoo",
                updated_at=utc_now_iso(),
                error=None,
            )
        if error:
            errors.append(error)

        return self._error_result(
            normalized_symbol,
            "; ".join(errors) or f"No price data found for symbol: {normalized_symbol}",
        )

    def _get_price_with_yfinance(self, symbol: str) -> tuple[float | None, str | None]:
        try:
            ticker = yf.Ticker(symbol)

            fast_info = getattr(ticker, "fast_info", None) or {}
            for key in ("last_price", "regular_market_price", "previous_close"):
                price = self._clean_price(self._safe_get(fast_info, key))
                if price is not None:
                    return price, None

            history = ticker.history(period="5d")
            if history.empty or "Close" not in history:
                return None, f"No yfinance history for symbol: {symbol}"

            close_prices = history["Close"].dropna()
            if close_prices.empty:
                return None, f"No yfinance close price for symbol: {symbol}"

            return self._clean_price(close_prices.iloc[-1]), None
        except Exception as exc:
            return None, f"yfinance failed: {exc}"

    def _get_price_with_quote_api(self, symbol: str) -> tuple[float | None, str | None]:
        try:
            response = requests.get(
                self.QUOTE_URL,
                params={"symbols": symbol},
                headers={"User-Agent": "IXAI-Agent/1.0"},
                timeout=8,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("quoteResponse", {}).get("result", [])
            if not results:
                return None, f"Yahoo quote API returned no data for symbol: {symbol}"

            quote = results[0]
            for key in ("regularMarketPrice", "postMarketPrice", "preMarketPrice"):
                price = self._clean_price(quote.get(key))
                if price is not None:
                    return price, None

            return None, f"Yahoo quote API returned no usable price for symbol: {symbol}"
        except Exception as exc:
            return None, f"Yahoo quote API failed: {exc}"

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            return []

        if self._looks_like_taiwan_query(text):
            results = self._search_tw_autocomplete(text, limit)
            if results:
                return results

        results = self._search_finance_api(text, limit)
        if results:
            return results

        return self._search_tw_autocomplete(text, limit)

    def _looks_like_taiwan_query(self, query: str) -> bool:
        text = query.strip().upper()
        base_symbol = text.removesuffix(".TW").removesuffix(".TWO")
        return (
            any(ord(char) > 127 for char in text)
            or text.endswith((".TW", ".TWO"))
            or (base_symbol.isdigit() and len(base_symbol) == 4)
        )

    def _search_finance_api(self, query: str, limit: int) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={
                    "q": query,
                    "quotesCount": limit,
                    "newsCount": 0,
                    "enableFuzzyQuery": "true",
                    "lang": "zh-TW",
                    "region": "TW",
                },
                headers={"User-Agent": "IXAI-Agent/1.0"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        quotes = data.get("quotes", [])
        if not isinstance(quotes, list):
            return []

        results: list[dict[str, Any]] = []
        for quote in quotes[:limit]:
            if not isinstance(quote, dict):
                continue

            symbol = str(quote.get("symbol") or "").strip().upper()
            if not symbol:
                continue

            results.append(
                {
                    "symbol": symbol,
                    "shortname": quote.get("shortname"),
                    "longname": quote.get("longname"),
                    "exchange": quote.get("exchange"),
                    "quoteType": quote.get("quoteType"),
                }
            )

        return results

    def _search_tw_autocomplete(self, query: str, limit: int) -> list[dict[str, Any]]:
        try:
            encoded_query = url_quote(query)
            response = requests.get(
                f"{self.TW_AUTOCOMPLETE_URL};query={encoded_query}",
                headers={"User-Agent": "IXAI-Agent/1.0"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        quotes = data.get("ResultSet", {}).get("Result", [])
        if not isinstance(quotes, list):
            return []

        results: list[dict[str, Any]] = []
        for quote in quotes[:limit]:
            if not isinstance(quote, dict):
                continue

            symbol = str(quote.get("symbol") or "").strip().upper()
            if not symbol:
                continue

            results.append(
                {
                    "symbol": symbol,
                    "shortname": quote.get("name"),
                    "longname": quote.get("name"),
                    "exchange": quote.get("exch"),
                    "quoteType": "EQUITY" if quote.get("type") == "S" else quote.get("type"),
                }
            )

        return results

    def _error_result(self, symbol: str, error: str) -> MarketPriceResult:
        return MarketPriceResult(
            symbol=symbol,
            price=None,
            source="yahoo",
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

    def _safe_get(self, data: Any, key: str) -> Any:
        try:
            return data.get(key)
        except AttributeError:
            return getattr(data, key, None)


class YahooProvider(YahooFinanceProvider):
    """Backward-compatible float-returning provider for existing services."""

    def get_price(self, symbol: str) -> float:
        result = super().get_price(symbol)
        if result.price is None:
            raise ValueError(result.error or f"No price data found for symbol: {symbol}")
        return result.price
