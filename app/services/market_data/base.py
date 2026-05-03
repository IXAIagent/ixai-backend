from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class MarketPriceResult:
    symbol: str
    price: float | None
    source: str
    updated_at: str
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MarketDataProvider(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> MarketPriceResult:
        """Return latest available price for a market symbol."""
        raise NotImplementedError
