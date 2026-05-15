from __future__ import annotations

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import IntelligenceScore, LongMemorySummary, PredictiveDrift, ThemeEvolution, WorkspaceDecision


class PredictiveDriftEngine:
    def predict(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        memory: LongMemorySummary,
        themes: ThemeEvolution,
    ) -> PredictiveDrift:
        try:
            shift = self._likely_shift(scores, workspace, memory, themes)
            confidence = self._confidence(scores, memory)
            reason = self._reason(shift, scores, memory, themes)
            alerts = self._alerts(scores, memory, themes)
            return PredictiveDrift(
                likely_workspace_shift=shift,
                confidence=confidence,
                prediction_reason=compliance_filter.sanitize_text(reason),
                predictive_alerts=compliance_filter.sanitize_list(alerts),
            )
        except Exception:
            return PredictiveDrift(prediction_reason="Predictive drift 暫時資料不足，維持保守監控。")

    def _likely_shift(
        self,
        scores: IntelligenceScore,
        workspace: WorkspaceDecision,
        memory: LongMemorySummary,
        themes: ThemeEvolution,
    ) -> str:
        if scores.fcn_risk_score >= 50 or memory.fcn_risk_trend == "RISING":
            return "FCN_RISK"
        if scores.crypto_vol_score >= 50 or memory.crypto_vol_trend == "RISING":
            return "CRYPTO_VOL"
        if scores.ai_momentum_score >= 50 and "AI_INFRA" in themes.dominant_themes:
            return "AI_MOMENTUM"
        if scores.macro_risk_score >= 50 or memory.historical_risk_trend == "RISING":
            return "DEFENSIVE"
        return workspace.workspace_mode or "BALANCED"

    def _confidence(self, scores: IntelligenceScore, memory: LongMemorySummary) -> float:
        base = 35.0
        base += min(scores.total_score / 3, 30)
        if memory.historical_risk_trend != "STABLE":
            base += 10
        return round(min(base, 75.0), 2)

    def _reason(
        self,
        shift: str,
        scores: IntelligenceScore,
        memory: LongMemorySummary,
        themes: ThemeEvolution,
    ) -> str:
        return (
            f"Likely workspace may lean toward {shift} because total score is {scores.total_score:.0f}, "
            f"historical trend is {memory.historical_risk_trend}, and themes are {', '.join(themes.dominant_themes[:3]) or 'mixed'}."
        )

    def _alerts(self, scores: IntelligenceScore, memory: LongMemorySummary, themes: ThemeEvolution) -> list[str]:
        alerts: list[str] = []
        if scores.fcn_risk_score >= 45:
            alerts.append("FCN risk may remain elevated if worst-of pressure continues.")
        if scores.crypto_vol_score >= 45:
            alerts.append("Crypto volatility expansion remains possible.")
        if scores.ai_momentum_score >= 45 and memory.ai_momentum_trend == "COOLING":
            alerts.append("AI momentum could rotate if positive flow weakens.")
        if "RATE_PRESSURE" in themes.dominant_themes:
            alerts.append("Rate pressure may push workspace toward defensive monitoring.")
        return alerts[:4] or ["No strong predictive alert detected."]
