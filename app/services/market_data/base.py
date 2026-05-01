from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """Return latest available price for a market symbol."""
        raise NotImplementedError
