from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import IntelligenceRunLog, Portfolio
from app.services.intelligence.service import PortfolioIntelligenceService


SOURCE = "scheduler"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _short_error(error: Exception | str, limit: int = 1000) -> str:
    return str(error)[:limit]


def run_intelligence_scheduler_once(db: Session | None = None, source: str = SOURCE) -> dict[str, Any]:
    owns_session = db is None
    session = db or SessionLocal()
    started_at = _utcnow()
    result: dict[str, Any] = {
        "status": "success",
        "source": source,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    try:
        limit = max(1, int(settings.INTELLIGENCE_SCHEDULER_BATCH_LIMIT or 100))
        portfolios = (
            session.query(Portfolio)
            .order_by(Portfolio.created_at.asc())
            .limit(limit)
            .all()
        )
        if not portfolios:
            result["status"] = "skipped"
            result["skipped"] = 0
            return result

        service = PortfolioIntelligenceService(
            session,
            skip_news=bool(settings.INTELLIGENCE_SCHEDULER_SKIP_NEWS),
        )
        for portfolio in portfolios:
            result["processed"] += 1
            run_log = IntelligenceRunLog(
                portfolio_id=str(portfolio.id),
                started_at=_utcnow(),
                status="failed",
                source=source,
            )
            session.add(run_log)
            session.flush()

            try:
                response = service.get_portfolio_summary_v2a(portfolio)
                if getattr(response, "is_stale", False):
                    run_log.status = "failed"
                    run_log.error = "Intelligence response was stale/fail-soft."
                    result["failed"] += 1
                    result["errors"].append(
                        {"portfolio_id": str(portfolio.id), "error": run_log.error}
                    )
                else:
                    run_log.status = "success"
                    result["success"] += 1
            except Exception as exc:
                run_log.status = "failed"
                run_log.error = _short_error(exc)
                result["failed"] += 1
                result["errors"].append(
                    {"portfolio_id": str(portfolio.id), "error": run_log.error}
                )
            finally:
                run_log.finished_at = _utcnow()
                session.add(run_log)
                session.commit()

        if result["failed"] and result["success"]:
            result["status"] = "completed_with_errors"
        elif result["failed"] and not result["success"]:
            result["status"] = "failed"
        return result
    except Exception as exc:
        session.rollback()
        result["status"] = "failed"
        result["errors"].append({"portfolio_id": None, "error": _short_error(exc)})
        return result
    finally:
        result["finished_at"] = _utcnow().isoformat()
        if owns_session:
            session.close()


def main() -> None:
    result = run_intelligence_scheduler_once()
    print(
        "IXAI intelligence scheduler finished:",
        {
            "status": result["status"],
            "processed": result["processed"],
            "success": result["success"],
            "failed": result["failed"],
            "skipped": result["skipped"],
        },
    )
    if result["errors"]:
        print("Errors:", result["errors"])


if __name__ == "__main__":
    main()
