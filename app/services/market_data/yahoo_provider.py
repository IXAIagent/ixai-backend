import yfinance as yf

from .base import MarketDataProvider


class YahooProvider(MarketDataProvider):
    def get_price(self, symbol: str) -> float:
        symbol = symbol.upper().strip()

        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1d")

        if history.empty or "Close" not in history:
            raise ValueError(f"No price data found for symbol: {symbol}")

        close_prices = history["Close"].dropna()
        if close_prices.empty:
            raise ValueError(f"No price data found for symbol: {symbol}")

        return float(close_prices.iloc[-1])
