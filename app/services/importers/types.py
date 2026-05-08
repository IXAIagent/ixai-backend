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


@dataclass
class ImportPreviewRow:
    row: int
    asset_type: str | None
    input_symbol: str | None
    canonical_symbol: str | None
    display_name: str | None
    action: Literal["import", "update", "skip"]
    quantity: float | None = None
    avg_price: float | None = None
    current_price: float | None = None
    currency: str | None = None
    amount: float | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "asset_type": self.asset_type,
            "input_symbol": self.input_symbol,
            "canonical_symbol": self.canonical_symbol,
            "display_name": self.display_name,
            "action": self.action,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "currency": self.currency,
            "amount": self.amount,
            "errors": self.errors,
        }


@dataclass
class ImportPreviewResult:
    rows: list[ImportPreviewRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        will_import = sum(1 for row in self.rows if row.action == "import")
        will_update = sum(1 for row in self.rows if row.action == "update")
        will_skip = sum(1 for row in self.rows if row.action == "skip")
        errors = sum(1 for row in self.rows if row.errors)

        return {
            "status": "preview",
            "rows": [row.to_dict() for row in self.rows],
            "summary": {
                "will_import": will_import,
                "will_update": will_update,
                "will_skip": will_skip,
                "errors": errors,
            },
        }
