from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SupportedImportAssetType = Literal["stock", "crypto", "cash"]


@dataclass
class ImportErrorItem:
    row: int
    error: str


@dataclass
class NormalizedImportPosition:
    row: int
    asset_type: SupportedImportAssetType
    symbol: str | None = None
    quantity: float | None = None
    avg_price: float | None = None
    current_price: float | None = None
    currency: str | None = None
    amount: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ImportErrorItem] = field(default_factory=list)

    def add_error(self, row: int, error: str) -> None:
        self.skipped += 1
        self.errors.append(ImportErrorItem(row=row, error=error))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "imported": self.imported,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": [
                {"row": item.row, "error": item.error}
                for item in self.errors
            ],
        }
