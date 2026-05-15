from __future__ import annotations

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import LongMemorySummary, ThemeEvolution, TimelineSummary, WorkspaceDecision
from app.services.news.schemas import NewsArticle


class IntelligenceTimelineEngine:
    def summarize(
        self,
        workspace: WorkspaceDecision,
        memory: LongMemorySummary,
        themes: ThemeEvolution,
        alerts: list[NewsArticle],
        what_changed_today: str,
    ) -> TimelineSummary:
        try:
            new_risks = []
            if workspace.workspace_mode != memory.dominant_workspace_mode:
                new_risks.append(f"Workspace shifted from historical {memory.dominant_workspace_mode} to {workspace.workspace_mode}.")
            if themes.emerging_themes:
                new_risks.append(f"Emerging themes: {', '.join(themes.emerging_themes[:3])}.")

            improving = []
            if memory.historical_risk_trend == "COOLING":
                improving.append("Historical risk trend is cooling.")
            if memory.crypto_vol_trend == "COOLING":
                improving.append("Crypto volatility trend is cooling.")

            persistent = themes.dominant_themes[:4] or memory.recurring_risk_themes[:4]
            events = [
                f"{str(alert.symbol or 'Portfolio')} {str(alert.priority_level or 'priority')} alert"
                for alert in alerts[:4]
            ]
            if not events:
                events.append("No high-priority timeline event detected.")

            weekly = self._weekly(memory, themes)
            return TimelineSummary(
                what_changed_today=compliance_filter.sanitize_text(what_changed_today),
                what_changed_this_week=compliance_filter.sanitize_text(weekly),
                new_risks=compliance_filter.sanitize_list(new_risks or ["No new risk cluster detected."]),
                improving_signals=compliance_filter.sanitize_list(improving or ["No clear improving signal detected."]),
                persistent_themes=persistent,
                timeline_events=compliance_filter.sanitize_list(events),
            )
        except Exception:
            return TimelineSummary(
                what_changed_today="Timeline intelligence 暫時資料不足。",
                what_changed_this_week="目前沒有足夠歷史資料判斷本週變化。",
            )

    def _weekly(self, memory: LongMemorySummary, themes: ThemeEvolution) -> str:
        parts = []
        if memory.historical_risk_trend != "STABLE":
            parts.append(f"historical risk trend is {memory.historical_risk_trend}")
        if memory.fcn_risk_trend != "STABLE":
            parts.append(f"FCN risk trend is {memory.fcn_risk_trend}")
        if themes.emerging_themes:
            parts.append(f"emerging themes include {', '.join(themes.emerging_themes[:3])}")
        return "; ".join(parts) or "This week remains stable versus stored intelligence memory."
