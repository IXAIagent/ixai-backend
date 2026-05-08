from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import ImportBatch, ImportRow, Portfolio, User
from app.services.importers.types import ImportPreviewRow, ImportResult


def create_import_audit_batch(
    db: Session,
    user: User,
    portfolio: Portfolio,
    file_name: str | None,
    result: ImportResult,
    preview_rows: list[ImportPreviewRow],
) -> ImportBatch:
    batch = ImportBatch(
        user_id=user.id,
        portfolio_id=portfolio.id,
        import_type="portfolio_csv",
        file_name=_safe_file_name(file_name),
        imported=result.imported,
        updated=result.updated,
        skipped=result.skipped,
        errors_count=len(result.errors),
        status=_batch_status(result),
    )
    db.add(batch)
    db.flush()

    rows_by_number = {row.row: row for row in preview_rows}
    error_by_row = {item.row: item.error for item in result.errors}
    row_numbers = sorted(set(rows_by_number) | set(error_by_row))

    for row_number in row_numbers:
        preview_row = rows_by_number.get(row_number)
        error_message = error_by_row.get(row_number) or _preview_error(preview_row)
        db.add(
            ImportRow(
                batch_id=batch.id,
                row_number=row_number,
                asset_type=preview_row.asset_type if preview_row else None,
                input_symbol=preview_row.input_symbol if preview_row else None,
                canonical_symbol=preview_row.canonical_symbol if preview_row else None,
                action=preview_row.action if preview_row else "skip",
                status="error" if error_message else "success",
                error_message=_truncate_error(error_message),
            )
        )

    db.commit()
    db.refresh(batch)
    return batch


def list_import_batches(db: Session, user: User, limit: int = 20) -> list[ImportBatch]:
    safe_limit = max(1, min(limit, 100))
    return (
        db.query(ImportBatch)
        .filter(ImportBatch.user_id == user.id)
        .order_by(ImportBatch.created_at.desc())
        .limit(safe_limit)
        .all()
    )


def get_import_batch_detail(db: Session, user: User, batch_id: str) -> ImportBatch | None:
    return (
        db.query(ImportBatch)
        .filter(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == user.id,
        )
        .first()
    )


def serialize_import_batch(batch: ImportBatch) -> dict:
    return {
        "id": batch.id,
        "import_type": batch.import_type,
        "file_name": batch.file_name,
        "imported": batch.imported,
        "updated": batch.updated,
        "skipped": batch.skipped,
        "errors_count": batch.errors_count,
        "status": batch.status,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


def serialize_import_batch_detail(batch: ImportBatch) -> dict:
    data = serialize_import_batch(batch)
    data["rows"] = [
        {
            "row_number": row.row_number,
            "asset_type": row.asset_type,
            "input_symbol": row.input_symbol,
            "canonical_symbol": row.canonical_symbol,
            "action": row.action,
            "status": row.status,
            "error_message": row.error_message,
        }
        for row in sorted(batch.rows, key=lambda item: item.row_number)
    ]
    return data


def _batch_status(result: ImportResult) -> str:
    errors_count = len(result.errors)
    if errors_count == 0:
        return "completed"
    if result.imported > 0 or result.updated > 0:
        return "completed_with_errors"
    return "failed"


def _preview_error(row: ImportPreviewRow | None) -> str | None:
    if not row or not row.errors:
        return None
    return "; ".join(row.errors)


def _truncate_error(error: str | None) -> str | None:
    if not error:
        return None
    return str(error)[:500]


def _safe_file_name(file_name: str | None) -> str | None:
    if not file_name:
        return None
    return str(file_name).split("/")[-1].split("\\")[-1][:255]
