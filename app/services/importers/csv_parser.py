from __future__ import annotations

import csv
from io import StringIO

from app.services.importers.types import ImportErrorItem

CSV_COLUMNS = {
    "asset_type",
    "symbol",
    "quantity",
    "avg_price",
    "current_price",
    "currency",
    "amount",
}


def parse_portfolio_csv(content: bytes) -> tuple[list[dict[str, str]], list[ImportErrorItem]]:
    errors: list[ImportErrorItem] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [ImportErrorItem(row=0, error="CSV must be UTF-8 encoded")]

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        return [], [ImportErrorItem(row=0, error="CSV header is required")]

    headers = {str(name or "").strip() for name in reader.fieldnames}
    missing = sorted(CSV_COLUMNS - headers)
    if missing:
        return [], [ImportErrorItem(row=0, error=f"missing columns: {', '.join(missing)}")]

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        cleaned = {
            column: str(row.get(column) or "").strip()
            for column in CSV_COLUMNS
        }
        if not any(cleaned.values()):
            continue
        rows.append({"_row": str(row_number), **cleaned})

    return rows, errors
