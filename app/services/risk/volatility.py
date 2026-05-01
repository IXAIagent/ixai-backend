from __future__ import annotations

from math import sqrt

import yfinance as yf

from app.services.market_data.yahoo_provider import YahooProvider


TRADING_DAYS_PER_YEAR = 252


class _YahooHistoryProvider(YahooProvider):
    def get_close_prices(self, symbol: str, days: int):
        normalized_symbol = _normalize_symbol(symbol)
        history = yf.Ticker(normalized_symbol).history(period=f"{days}d")

        if history.empty or "Close" not in history:
            raise ValueError(
                f"No historical close data found for symbol: {normalized_symbol}"
            )

        close_prices = history["Close"].dropna().tail(days)
        if len(close_prices) < 2:
            raise ValueError(
                "Not enough historical close data to calculate volatility "
                f"for symbol: {normalized_symbol}"
            )

        return close_prices


def calculate_volatility(symbol: str, days: int = 30) -> float:
    normalized_symbol = _normalize_symbol(symbol)
    validated_days = _validate_days(days)

    provider = _YahooHistoryProvider()
    close_prices = provider.get_close_prices(normalized_symbol, validated_days)
    daily_returns = close_prices.pct_change().dropna()

    if daily_returns.empty:
        raise ValueError(
            f"Not enough daily returns to calculate volatility for symbol: {normalized_symbol}"
        )

    std = daily_returns.std()
    if std != std:
        raise ValueError(f"Volatility calculation failed for symbol: {normalized_symbol}")

    return float(std * sqrt(TRADING_DAYS_PER_YEAR))


def _normalize_symbol(symbol: str) -> str:
    if not symbol or not symbol.strip():
        raise ValueError("Symbol is required")

    return symbol.strip().upper()


def _validate_days(days: int) -> int:
    try:
        validated_days = int(days)
    except (TypeError, ValueError) as exc:
        raise ValueError("days must be an integer") from exc

    if validated_days < 2:
        raise ValueError("days must be at least 2")

    return validated_days
