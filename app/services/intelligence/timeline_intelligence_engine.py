from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.persistent_memory import IntelligenceMemoryStore
from app.services.intelligence.schemas import TimelineIntelligenceResponse, TimelineWindowSummary


class TimelineIntelligenceEngine:
    def __init__(self, store: IntelligenceMemoryStore | None = None) -> None:
        self.store = store or IntelligenceMemoryStore()

    def analyze(self, portfolio_id: str) -> TimelineIntelligenceResponse:
        now = datetime.now(timezone.utc)
        try:
            history = self._load_history(portfolio_id)
            if len(history) < 2:
                return self._fallback(str(portfolio_id), now, "歷史資料仍在累積，暫時無法形成可靠趨勢。")

            windows = [
                self._summarize_window("7d", history, now - timedelta(days=7)),
                self._summarize_window("30d", history, now - timedelta(days=30)),
                self._summarize_window("90d", history, now - timedelta(days=90)),
            ]
            primary = next((item for item in windows if item.window == "30d"), windows[0])
            usable_windows = [item for item in windows if item.risk_score_trend != "INSUFFICIENT_HISTORY"]
            confidence = min(95.0, 20.0 + len(history) * 5.0 + len(usable_windows) * 10.0)
            summary = self._build_timeline_summary(primary, confidence)

            return TimelineIntelligenceResponse(
                portfolio_id=str(portfolio_id),
                windows=windows,
                regime_evolution=primary.regime_evolution,
                exposure_evolution=primary.exposure_evolution,
                risk_score_trend=primary.risk_score_trend,
                concentration_trend=primary.concentration_trend,
                volatility_trend=primary.volatility_trend,
                dominant_driver_history=primary.dominant_driver_history,
                recurring_risks=primary.recurring_risks,
                improving_signals=primary.improving_signals,
                deteriorating_signals=primary.deteriorating_signals,
                timeline_summary=summary,
                message="Timeline intelligence generated.",
                confidence=round(confidence, 2),
                generated_at=now,
                is_stale=confidence < 45,
            )
        except Exception:
            return self._fallback(str(portfolio_id), now, "歷史資料讀取失敗，已回傳安全 fallback。")

    def _load_history(self, portfolio_id: str) -> list[dict[str, Any]]:
        raw_history = self.store.get_recent_history(str(portfolio_id), limit=200)
        parsed: list[dict[str, Any]] = []
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            created_at = self._parse_dt(item.get("generated_at"))
            if created_at is None:
                continue
            item["_created_at"] = created_at
            parsed.append(item)
        return sorted(parsed, key=lambda row: row["_created_at"])

    def _summarize_window(
        self,
        window: str,
        history: list[dict[str, Any]],
        since: datetime,
    ) -> TimelineWindowSummary:
        rows = [item for item in history if item["_created_at"] >= since]
        if len(rows) < 2:
            return TimelineWindowSummary(window=window)

        first = rows[0]
        last = rows[-1]
        drivers = self._unique_nonempty(row.get("dominant_driver") for row in rows)
        risks = self._recurring_risks(rows)
        improving, deteriorating = self._signals(first, last)

        return TimelineWindowSummary(
            window=window,
            regime_evolution=self._evolution(first.get("regime") or first.get("workspace_mode"), last.get("regime") or last.get("workspace_mode")),
            exposure_evolution=self._numeric_trend(first.get("concentration_score"), last.get("concentration_score"), "EXPOSURE"),
            risk_score_trend=self._numeric_trend(
                (first.get("scores") or {}).get("total_score"),
                (last.get("scores") or {}).get("total_score"),
                "RISK",
            ),
            concentration_trend=self._numeric_trend(first.get("concentration_score"), last.get("concentration_score"), "CONCENTRATION"),
            volatility_trend=self._evolution(first.get("volatility_state"), last.get("volatility_state")),
            dominant_driver_history=drivers[:8],
            recurring_risks=risks[:6],
            improving_signals=improving[:5],
            deteriorating_signals=deteriorating[:5],
        )

    def _build_timeline_summary(self, primary: TimelineWindowSummary, confidence: float) -> str:
        if confidence < 45:
            return "歷史資料仍在累積，目前僅能提供初步趨勢觀察。"
        parts = [
            f"近 30 天 regime 變化為 {primary.regime_evolution}。",
            f"風險分數趨勢為 {primary.risk_score_trend}，集中度趨勢為 {primary.concentration_trend}。",
        ]
        if primary.deteriorating_signals:
            parts.append(f"需要留意：{primary.deteriorating_signals[0]}。")
        elif primary.improving_signals:
            parts.append(f"改善訊號：{primary.improving_signals[0]}。")
        return compliance_filter.sanitize_text("".join(parts), max_length=240)

    def _fallback(self, portfolio_id: str, now: datetime, message: str) -> TimelineIntelligenceResponse:
        clean_message = compliance_filter.sanitize_text(message, max_length=180)
        return TimelineIntelligenceResponse(
            portfolio_id=portfolio_id,
            windows=[
                TimelineWindowSummary(window="7d"),
                TimelineWindowSummary(window="30d"),
                TimelineWindowSummary(window="90d"),
            ],
            timeline_summary=clean_message,
            message=clean_message,
            confidence=10,
            generated_at=now,
            is_stale=True,
        )

    def _evolution(self, first: Any, last: Any) -> str:
        first_text = str(first or "UNKNOWN").strip().upper()
        last_text = str(last or "UNKNOWN").strip().upper()
        if first_text == last_text:
            return f"STABLE:{last_text}"
        return f"{first_text} → {last_text}"

    def _numeric_trend(self, first: Any, last: Any, label: str) -> str:
        first_value = self._float(first)
        last_value = self._float(last)
        delta = last_value - first_value
        if delta >= 10:
            return f"{label}_RISING"
        if delta <= -10:
            return f"{label}_COOLING"
        return f"{label}_STABLE"

    def _signals(self, first: dict[str, Any], last: dict[str, Any]) -> tuple[list[str], list[str]]:
        improving: list[str] = []
        deteriorating: list[str] = []
        risk_delta = self._float((last.get("scores") or {}).get("total_score")) - self._float((first.get("scores") or {}).get("total_score"))
        concentration_delta = self._float(last.get("concentration_score")) - self._float(first.get("concentration_score"))
        if risk_delta <= -10:
            improving.append("整體 intelligence 風險分數下降")
        elif risk_delta >= 10:
            deteriorating.append("整體 intelligence 風險分數上升")
        if concentration_delta <= -10:
            improving.append("投資組合集中度下降")
        elif concentration_delta >= 10:
            deteriorating.append("投資組合集中度上升")
        if str(last.get("volatility_state") or "").upper() in {"HIGH_VOL", "ELEVATED"}:
            deteriorating.append("波動狀態偏高")
        return (
            compliance_filter.sanitize_list(improving),
            compliance_filter.sanitize_list(deteriorating),
        )

    def _recurring_risks(self, rows: list[dict[str, Any]]) -> list[str]:
        counts: dict[str, int] = {}
        for row in rows:
            driver = str(row.get("dominant_driver") or "").strip()
            if driver:
                counts[driver] = counts.get(driver, 0) + 1
            for alert in row.get("top_alerts") or []:
                title = str((alert or {}).get("title") or "").strip()
                if title:
                    counts[title] = counts.get(title, 0) + 1
        recurring = [key for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count >= 2]
        return compliance_filter.sanitize_list(recurring[:6])

    def _unique_nonempty(self, values) -> list[str]:
        seen: dict[str, None] = {}
        for value in values:
            text = compliance_filter.sanitize_text(value, max_length=100)
            if text:
                seen[text] = None
        return list(seen.keys())

    def _parse_dt(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
