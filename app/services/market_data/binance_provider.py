import requests

from .base import MarketDataProvider


class BinanceProvider(MarketDataProvider):
    BASE_URL = "https://api.binance.com/api/v3/ticker/price"

    def get_price(self, symbol: str = "BTCUSDT") -> float:
        symbol = symbol.upper().strip()

        try:
            response = requests.get(
                self.BASE_URL,
                params={"symbol": symbol},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            return float(data["price"])

        except Exception as e:
            raise ValueError(f"Binance price fetch failed: {e}")
