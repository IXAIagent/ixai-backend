from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import IntelligenceNarrative, IntelligenceScore, WorkspaceDecision
from app.services.news.schemas import NewsArticle


class IntelligenceMemoryStore:
    def __init__(self, base_dir: Path | None = None, max_snapshots: int = 50) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data" / "intelligence_memory"
        self.max_snapshots = max_snapshots

    def append_snapshot(
        self,
        portfolio_id: str,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        narrative: IntelligenceNarrative,
        top_alerts: list[NewsArticle],
    ) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            path = self._path(portfolio_id)
            history = self.get_recent_history(portfolio_id, limit=self.max_snapshots)
            history.append({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "workspace_mode": workspace.workspace_mode,
                "risk_drift": workspace.risk_drift,
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
                    for alert in top_alerts[:5]
                ],
            })
            path.write_text(
                json.dumps({"portfolio_id": portfolio_id, "snapshots": history[-self.max_snapshots:]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return

    def get_recent_history(self, portfolio_id: str, limit: int = 10) -> list[dict[str, Any]]:
        try:
            path = self._path(portfolio_id)
            if not path.exists():
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            snapshots = data.get("snapshots", [])
            if not isinstance(snapshots, list):
                return []
            return snapshots[-limit:]
        except Exception:
            return []

    def compare_historical_drift(self, portfolio_id: str, current_scores: IntelligenceScore) -> str:
        history = self.get_recent_history(portfolio_id, limit=5)
        if not history:
            return "目前沒有可比較的 persistent memory，已建立第一筆風險記憶。"
        previous_scores = history[-1].get("scores", {})
        previous_total = self._float(previous_scores.get("total_score"))
        delta = current_scores.total_score - previous_total
        if delta >= 10:
            return "相較上一筆記憶，整體 intelligence 風險分數上升。"
        if delta <= -10:
            return "相較上一筆記憶，整體 intelligence 風險分數下降。"
        return "相較上一筆記憶，整體 intelligence 風險分數大致穩定。"

    def detect_trend(self, portfolio_id: str) -> str:
        history = self.get_recent_history(portfolio_id, limit=5)
        totals = [self._float(item.get("scores", {}).get("total_score")) for item in history]
        if len(totals) < 3:
            return "INSUFFICIENT_HISTORY"
        if totals[-1] > totals[0] + 10:
            return "RISING_RISK"
        if totals[-1] < totals[0] - 10:
            return "COOLING_RISK"
        return "STABLE"

    def _path(self, portfolio_id: str) -> Path:
        safe_id = "".join(ch for ch in str(portfolio_id) if ch.isalnum() or ch in {"-", "_"})
        return self.base_dir / f"{safe_id}.json"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
