from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.intelligence.persistent_memory import IntelligenceMemoryStore
from app.services.intelligence.schemas import LongMemorySummary


class LongTermMemoryEngine:
    def __init__(self, store: IntelligenceMemoryStore | None = None) -> None:
        self.store = store or IntelligenceMemoryStore()

    def summarize(self, portfolio_id: str) -> LongMemorySummary:
        try:
            history = self.store.get_recent_history(portfolio_id, limit=90)
            if not history:
                return LongMemorySummary()
            windows = {
                "7d": self._within(history, 7),
                "30d": self._within(history, 30),
                "90d": self._within(history, 90),
            }
            primary = windows["30d"] or history
            workspace_counts = Counter(str(item.get("workspace_mode") or "BALANCED") for item in primary)
            dominant_workspace = workspace_counts.most_common(1)[0][0] if workspace_counts else "BALANCED"
            recurring = self._recurring_themes(primary)
            return LongMemorySummary(
                dominant_workspace_mode=dominant_workspace,
                recurring_risk_themes=recurring,
                historical_risk_trend=self._trend(primary, "total_score"),
                fcn_risk_trend=self._trend(primary, "fcn_risk_score"),
                crypto_vol_trend=self._trend(primary, "crypto_vol_score"),
                ai_momentum_trend=self._trend(primary, "ai_momentum_score"),
                concentration_trend=self._concentration_trend(primary),
            )
        except Exception:
            return LongMemorySummary()

    def _within(self, history: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = []
        for item in history:
            try:
                generated_at = datetime.fromisoformat(str(item.get("generated_at")).replace("Z", "+00:00"))
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone.utc)
                if generated_at >= cutoff:
                    rows.append(item)
            except Exception:
                continue
        return rows

    def _trend(self, history: list[dict[str, Any]], key: str) -> str:
        values = [self._float(item.get("scores", {}).get(key)) for item in history if item.get("scores")]
        if len(values) < 2:
            return "STABLE"
        delta = values[-1] - values[0]
        if delta >= 10:
            return "RISING"
        if delta <= -10:
            return "COOLING"
        return "STABLE"

    def _recurring_themes(self, history: list[dict[str, Any]]) -> list[str]:
        counts: Counter[str] = Counter()
        for item in history:
            mode = str(item.get("workspace_mode") or "")
            if mode and mode != "BALANCED":
                counts[mode] += 1
            risk_drift = str(item.get("risk_drift") or "")
            if risk_drift.upper().startswith("INCREAS"):
                counts["RISK_DRIFT"] += 1
        return [theme for theme, _ in counts.most_common(5)]

    def _concentration_trend(self, history: list[dict[str, Any]]) -> str:
        # Phase 6 MVP has no persistent concentration metric yet; infer from repeated workspace stress.
        risky = sum(1 for item in history if str(item.get("workspace_mode") or "") in {"FCN_RISK", "AI_MOMENTUM", "CRYPTO_VOL"})
        if risky >= max(3, len(history) // 2):
            return "CONCENTRATED"
        return "STABLE"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
