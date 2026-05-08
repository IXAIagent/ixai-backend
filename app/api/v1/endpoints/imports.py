from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Portfolio, User
from app.services.importers import import_positions_batch, parse_portfolio_csv

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
        return {
            "status": "ok",
            "imported": 0,
            "updated": 0,
            "skipped": len(parse_errors),
            "errors": [
                {"row": error.row, "error": error.error}
                for error in parse_errors
            ],
        }

    portfolio = _get_or_create_user_portfolio(db, current_user)
    result = import_positions_batch(db, portfolio, rows)
    return result.to_dict()


def _validate_csv_file(file: UploadFile) -> None:
    filename = str(file.filename or "").lower()
    content_type = str(file.content_type or "").lower()

    if not filename.endswith(".csv") and content_type not in CSV_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only CSV files are supported")


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
