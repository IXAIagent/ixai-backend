from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import CashPosition, CryptoPosition, Portfolio, StockPosition
from app.services.importers.types import ImportResult, NormalizedImportPosition
from app.services.normalization import normalize_asset_symbol
from app.services.resolver import resolve_asset


def import_positions_batch(
    db: Session,
    portfolio: Portfolio,
    rows: list[dict[str, str]],
) -> ImportResult:
    result = ImportResult()

    for row in rows:
        position = normalize_imported_position(row)
        if isinstance(position, str):
            result.add_error(_row_number(row), position)
            continue

        try:
            created = import_position_to_portfolio(db, portfolio, position)
            if created:
                result.imported += 1
            else:
                result.updated += 1
        except Exception as exc:
            db.rollback()
            result.add_error(position.row, f"import failed: {exc.__class__.__name__}")

    db.commit()
    return result


def normalize_imported_position(row: dict[str, str]) -> NormalizedImportPosition | str:
    row_number = _row_number(row)
    asset_type = _clean(row.get("asset_type")).lower()

    if asset_type == "fcn":
        return "unsupported asset_type fcn"

    if asset_type not in {"stock", "crypto", "cash"}:
        return f"unsupported asset_type {asset_type or 'blank'}"

    if asset_type == "cash":
        currency = _clean(row.get("currency")).upper()
        amount = _parse_float(row.get("amount"))
        if not currency:
            return "currency is required for cash"
        if amount is None:
            return "amount is required for cash"
        return NormalizedImportPosition(
            row=row_number,
            asset_type="cash",
            currency=currency,
            amount=amount,
            raw=_safe_raw(row),
        )

    symbol = _clean(row.get("symbol"))
    quantity = _parse_float(row.get("quantity"))
    avg_price = _parse_float(row.get("avg_price"))
    current_price = _parse_float(row.get("current_price"))

    if not symbol:
        return "symbol is required"
    if quantity is None:
        return "quantity is required"

    if asset_type == "stock":
        resolved = resolve_asset(symbol, "stock")
        canonical_symbol = resolved.get("canonical_symbol")
        if not canonical_symbol:
            if not _looks_like_ticker(symbol):
                return "symbol could not be resolved"
            canonical_symbol = normalize_asset_symbol(symbol, "stock")
        symbol = str(canonical_symbol).upper()
    else:
        symbol = normalize_asset_symbol(symbol, "crypto")

    return NormalizedImportPosition(
        row=row_number,
        asset_type=asset_type,  # type: ignore[arg-type]
        symbol=symbol,
        quantity=quantity,
        avg_price=avg_price,
        current_price=current_price,
        raw=_safe_raw(row),
    )


def import_position_to_portfolio(
    db: Session,
    portfolio: Portfolio,
    position: NormalizedImportPosition,
) -> bool:
    if position.asset_type == "stock":
        return _upsert_stock(db, portfolio, position)
    if position.asset_type == "crypto":
        return _upsert_crypto(db, portfolio, position)
    if position.asset_type == "cash":
        return _upsert_cash(db, portfolio, position)

    raise ValueError(f"unsupported asset_type {position.asset_type}")


def _upsert_stock(db: Session, portfolio: Portfolio, position: NormalizedImportPosition) -> bool:
    stock = (
        db.query(StockPosition)
        .filter(
            StockPosition.portfolio_id == portfolio.id,
            StockPosition.symbol == position.symbol,
        )
        .first()
    )
    created = stock is None

    if stock is None:
        stock = StockPosition(portfolio_id=portfolio.id, symbol=position.symbol or "")
        db.add(stock)

    stock.quantity = position.quantity or 0
    stock.avg_price = position.avg_price or 0
    stock.current_price = position.current_price
    stock.current_value = _current_value(position.quantity, position.current_price)
    return created


def _upsert_crypto(db: Session, portfolio: Portfolio, position: NormalizedImportPosition) -> bool:
    crypto = (
        db.query(CryptoPosition)
        .filter(
            CryptoPosition.portfolio_id == portfolio.id,
            CryptoPosition.symbol == position.symbol,
            CryptoPosition.asset_type == "crypto",
        )
        .first()
    )
    created = crypto is None

    if crypto is None:
        crypto = CryptoPosition(
            portfolio_id=portfolio.id,
            symbol=position.symbol or "",
            asset_type="crypto",
        )
        db.add(crypto)

    crypto.quantity = position.quantity or 0
    crypto.avg_price = position.avg_price
    crypto.current_price = position.current_price
    crypto.current_value = _current_value(position.quantity, position.current_price)
    return created


def _upsert_cash(db: Session, portfolio: Portfolio, position: NormalizedImportPosition) -> bool:
    cash = (
        db.query(CashPosition)
        .filter(
            CashPosition.portfolio_id == portfolio.id,
            CashPosition.currency == position.currency,
        )
        .first()
    )
    created = cash is None

    if cash is None:
        cash = CashPosition(
            portfolio_id=portfolio.id,
            currency=position.currency or "USD",
        )
        db.add(cash)

    cash.amount = position.amount or 0
    return created


def _current_value(quantity: float | None, current_price: float | None) -> float | None:
    if quantity is None or current_price is None:
        return None
    return quantity * current_price


def _parse_float(value: str | None) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _looks_like_ticker(symbol: str) -> bool:
    text = symbol.strip().upper()
    compact = text.replace(".", "").replace("-", "")
    return bool(compact) and compact.isascii() and compact.isalnum()


def _row_number(row: dict[str, str]) -> int:
    try:
        return int(row.get("_row") or 0)
    except ValueError:
        return 0


def _safe_raw(row: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in row.items()
        if key in {"asset_type", "symbol", "currency"}
    }
