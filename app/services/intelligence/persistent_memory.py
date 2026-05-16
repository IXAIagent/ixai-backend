"""Intelligence long-term memory store backed by PostgreSQL.

Replaces the legacy `data/intelligence_memory/{portfolio_id}.json` files
with the `intelligence_memory_snapshots` table so memory survives Render
restarts and is shared across workers.

Preserves the public `IntelligenceMemoryStore` API
(`append_snapshot`, `get_recent_history`, `compare_historical_drift`,
`detect_trend`) so existing callers (`long_memory.py`, `service.py`) are
unaffected.

Fail-soft: every DB access is wrapped in try/except + `logger.exception`,
so intelligence endpoints never 500 because of memory persistence errors.
The `base_dir` constructor argument is accepted for backward compatibility
but is no longer used.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import IntelligenceMemorySnapshot
from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import (
    IntelligenceNarrative,
    IntelligenceScore,
    WorkspaceDecision,
)
from app.services.news.schemas import NewsArticle

logger = logging.getLogger(__name__)


class IntelligenceMemoryStore:
    def __init__(
        self,
        base_dir: Path | None = None,
        max_snapshots: int = 50,
        db: Session | None = None,
    ) -> None:
        # base_dir retained for API compatibility; persistence is now via DB.
        self.base_dir = base_dir
        self.max_snapshots = max(1, int(max_snapshots or 1))
        self.db = db

    # ------------------------------------------------------------------
    # write path
    # ------------------------------------------------------------------
    def append_snapshot(
        self,
        portfolio_id: str,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        narrative: IntelligenceNarrative,
        top_alerts: list[NewsArticle],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            payload = self._build_payload(scores, workspace, narrative, top_alerts, metadata or {})
        except Exception:
            logger.exception("intelligence_memory snapshot build failed")
            return

        db, owns_session = self._get_db()
        try:
            record = IntelligenceMemorySnapshot(
                portfolio_id=str(portfolio_id),
                snapshot=json.dumps(payload, ensure_ascii=False),
                workspace_mode=str(workspace.workspace_mode or "") or None,
                total_score=self._float(getattr(scores, "total_score", None)),
                risk_drift=str(workspace.risk_drift or "") or None,
                regime=str((metadata or {}).get("regime") or "") or None,
                concentration_score=self._float((metadata or {}).get("concentration_score")),
                dominant_driver=str((metadata or {}).get("dominant_driver") or "") or None,
                volatility_state=str((metadata or {}).get("volatility_state") or "") or None,
            )
            db.add(record)
            db.commit()
            self._trim_old_snapshots(db, str(portfolio_id))
        except Exception:
            logger.exception("intelligence_memory append failed")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            if owns_session:
                try:
                    db.close()
                except Exception:
                    pass

    def _build_payload(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        narrative: IntelligenceNarrative,
        top_alerts: list[NewsArticle],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace_mode": workspace.workspace_mode,
            "risk_drift": workspace.risk_drift,
            "regime": (metadata or {}).get("regime"),
            "concentration_score": (metadata or {}).get("concentration_score"),
            "dominant_driver": (metadata or {}).get("dominant_driver"),
            "volatility_state": (metadata or {}).get("volatility_state"),
            "scores": scores.model_dump(),
            "narrative": {
                key: compliance_filter.sanitize_text(value)
                for key, value in narrative.model_dump().items()
            },
            "top_alerts": [
                {
                    "symbol": str(alert.symbol or ""),
                    "priority_level": str(alert.priority_level or ""),
                    "title": compliance_filter.sanitize_text(alert.title, max_length=160),
                }
                for alert in (top_alerts or [])[:5]
            ],
        }

    def _trim_old_snapshots(self, db, portfolio_id: str) -> None:
        try:
            total = (
                db.query(IntelligenceMemorySnapshot)
                .filter(IntelligenceMemorySnapshot.portfolio_id == portfolio_id)
                .count()
            )
            if total <= self.max_snapshots:
                return
            excess = total - self.max_snapshots
            oldest_ids = [
                row.id
                for row in (
                    db.query(IntelligenceMemorySnapshot.id)
                    .filter(IntelligenceMemorySnapshot.portfolio_id == portfolio_id)
                    .order_by(IntelligenceMemorySnapshot.created_at.asc())
                    .limit(excess)
                    .all()
                )
            ]
            if oldest_ids:
                db.query(IntelligenceMemorySnapshot).filter(
                    IntelligenceMemorySnapshot.id.in_(oldest_ids)
                ).delete(synchronize_session=False)
                db.commit()
        except Exception:
            logger.exception("intelligence_memory trim failed")
            try:
                db.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # read path
    # ------------------------------------------------------------------
    def get_recent_history(self, portfolio_id: str, limit: int = 10) -> list[dict[str, Any]]:
        clamped_limit = max(1, int(limit or 1))
        db, owns_session = self._get_db()
        try:
            rows = (
                db.query(IntelligenceMemorySnapshot)
                .filter(IntelligenceMemorySnapshot.portfolio_id == str(portfolio_id))
                .order_by(IntelligenceMemorySnapshot.created_at.desc())
                .limit(clamped_limit)
                .all()
            )
            # newest-first from DB; reverse so callers see oldest within
            # the recent-N window first (matches legacy JSON-file behaviour).
            rows.reverse()
            result: list[dict[str, Any]] = []
            for row in rows:
                try:
                    parsed = json.loads(row.snapshot or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(parsed, dict):
                    result.append(parsed)
            return result
        except Exception:
            logger.exception("intelligence_memory read failed")
            return []
        finally:
            if owns_session:
                try:
                    db.close()
                except Exception:
                    pass

    def compare_historical_drift(
        self, portfolio_id: str, current_scores: IntelligenceScore
    ) -> str:
        history = self.get_recent_history(portfolio_id, limit=5)
        if not history:
            return "目前沒有可比較的 persistent memory，已建立第一筆風險記憶。"
        previous_scores = history[-1].get("scores", {}) or {}
        previous_total = self._float(previous_scores.get("total_score"))
        delta = self._float(getattr(current_scores, "total_score", 0)) - previous_total
        if delta >= 10:
            return "相較上一筆記憶，整體 intelligence 風險分數上升。"
        if delta <= -10:
            return "相較上一筆記憶，整體 intelligence 風險分數下降。"
        return "相較上一筆記憶，整體 intelligence 風險分數大致穩定。"

    def detect_trend(self, portfolio_id: str) -> str:
        history = self.get_recent_history(portfolio_id, limit=5)
        totals = [
            self._float((item.get("scores") or {}).get("total_score")) for item in history
        ]
        if len(totals) < 3:
            return "INSUFFICIENT_HISTORY"
        if totals[-1] > totals[0] + 10:
            return "RISING_RISK"
        if totals[-1] < totals[0] - 10:
            return "COOLING_RISK"
        return "STABLE"

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _get_db(self) -> tuple[Session, bool]:
        if self.db is not None:
            return self.db, False
        return SessionLocal(), True
