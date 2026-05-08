from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Portfolio, User
from app.services.importers import import_positions_batch, parse_portfolio_csv, preview_positions_batch
from app.services.importers.audit import (
    create_import_audit_batch,
    get_import_batch_detail,
    list_import_batches,
    serialize_import_batch,
    serialize_import_batch_detail,
)
from app.services.importers.types import ImportPreviewRow, ImportResult

router = APIRouter()

MAX_CSV_SIZE_BYTES = 2 * 1024 * 1024
CSV_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}


@router.post("/portfolio-csv")
async def import_portfolio_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_csv_file(file)

    content = await file.read(MAX_CSV_SIZE_BYTES + 1)
    if len(content) > MAX_CSV_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is too large")

    rows, parse_errors = parse_portfolio_csv(content)
    if parse_errors:
        portfolio = _get_or_create_user_portfolio(db, current_user)
        result = ImportResult()
        preview_rows = []
        for error in parse_errors:
            result.add_error(error.row, error.error)
            preview_rows.append(
                ImportPreviewRow(
                    row=error.row,
                    asset_type=None,
                    input_symbol=None,
                    canonical_symbol=None,
                    display_name=None,
                    action="skip",
                    errors=[error.error],
                )
            )
        batch = create_import_audit_batch(
            db,
            current_user,
            portfolio,
            file.filename,
            result,
            preview_rows,
        )
        response = result.to_dict()
        response["batch_id"] = batch.id
        return response

    portfolio = _get_or_create_user_portfolio(db, current_user)
    preview_result = preview_positions_batch(db, portfolio, rows)
    result = import_positions_batch(db, portfolio, rows)
    batch = create_import_audit_batch(
        db,
        current_user,
        portfolio,
        file.filename,
        result,
        preview_result.rows,
    )
    response = result.to_dict()
    response["batch_id"] = batch.id
    return response


@router.get("/history")
def get_import_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batches = list_import_batches(db, current_user, limit=limit)
    return {"items": [serialize_import_batch(batch) for batch in batches]}


@router.get("/history/{batch_id}")
def get_import_history_detail(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = get_import_batch_detail(db, current_user, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return serialize_import_batch_detail(batch)


@router.post("/portfolio-csv/preview")
async def preview_portfolio_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_csv_file(file)

    content = await file.read(MAX_CSV_SIZE_BYTES + 1)
    if len(content) > MAX_CSV_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="CSV file is too large")

    rows, parse_errors = parse_portfolio_csv(content)
    if parse_errors:
        return {
            "status": "preview",
            "rows": [
                {
                    "row": error.row,
                    "asset_type": None,
                    "input_symbol": None,
                    "canonical_symbol": None,
                    "display_name": None,
                    "action": "skip",
                    "quantity": None,
                    "avg_price": None,
                    "current_price": None,
                    "currency": None,
                    "amount": None,
                    "errors": [error.error],
                }
                for error in parse_errors
            ],
            "summary": {
                "will_import": 0,
                "will_update": 0,
                "will_skip": len(parse_errors),
                "errors": len(parse_errors),
            },
        }

    portfolio = _get_user_portfolio(db, current_user)
    result = preview_positions_batch(db, portfolio, rows)
    return result.to_dict()


def _validate_csv_file(file: UploadFile) -> None:
    filename = str(file.filename or "").lower()
    content_type = str(file.content_type or "").lower()

    if not filename.endswith(".csv") and content_type not in CSV_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only CSV files are supported")


def _get_user_portfolio(db: Session, user: User) -> Portfolio | None:
    return (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at.asc())
        .first()
    )


def _get_or_create_user_portfolio(db: Session, user: User) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at.asc())
        .first()
    )

    if portfolio:
        return portfolio

    portfolio = Portfolio(
        name="IXAI Portfolio",
        base_currency="USD",
        user_id=user.id,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio
