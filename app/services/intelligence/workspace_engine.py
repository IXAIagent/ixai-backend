from __future__ import annotations

from app.services.intelligence.schemas import IntelligenceScore, WorkspaceDecision


class WorkspaceDecisionEngine:
    def decide(self, scores: IntelligenceScore, critical_count: int = 0, high_count: int = 0) -> WorkspaceDecision:
        try:
            mode = self._workspace_mode(scores, critical_count)
            return WorkspaceDecision(
                workspace_mode=mode,
                primary_focus=self._primary_focus(mode, scores),
                risk_drift=self._risk_drift(scores, critical_count, high_count),
                market_regime=self._market_regime(mode, scores),
                decision_signals=self._decision_signals(mode, scores, critical_count, high_count),
            )
        except Exception:
            return WorkspaceDecision(
                workspace_mode="BALANCED",
                primary_focus="Portfolio stable · monitor alerts and concentration drift",
                risk_drift="Stable",
                market_regime="MIXED ROTATION",
                decision_signals=["WATCH"],
            )

    def _workspace_mode(self, scores: IntelligenceScore, critical_count: int) -> str:
        if scores.fcn_risk_score >= 55 or critical_count > 0:
            return "FCN_RISK"
        if scores.crypto_vol_score >= 55:
            return "CRYPTO_VOL"
        if scores.ai_momentum_score >= 55:
            return "AI_MOMENTUM"
        if scores.macro_risk_score >= 55 or scores.total_score >= 65:
            return "DEFENSIVE"
        return "BALANCED"

    def _primary_focus(self, mode: str, scores: IntelligenceScore) -> str:
        if mode == "FCN_RISK":
            return "FCN KI sensitivity / worst-of monitoring is the current priority."
        if mode == "AI_MOMENTUM":
            return "AI/chip momentum is dominating portfolio intelligence flow."
        if mode == "CRYPTO_VOL":
            return "Crypto volatility is elevated across portfolio context."
        if mode == "DEFENSIVE":
            return "Risk control posture is active; monitor macro and downside flow."
        return "Portfolio stable; monitor alerts, FCN distance and concentration drift."

    def _risk_drift(self, scores: IntelligenceScore, critical_count: int, high_count: int) -> str:
        if critical_count > 0 or scores.total_score >= 65:
            return "Increasing"
        if high_count > 0 or scores.total_score >= 40:
            return "Stable"
        return "Improving"

    def _market_regime(self, mode: str, scores: IntelligenceScore) -> str:
        if mode == "FCN_RISK":
            return "FCN RISK WATCH"
        if mode == "CRYPTO_VOL":
            return "CRYPTO VOL REGIME"
        if mode == "AI_MOMENTUM":
            return "RISK-ON AI MOMENTUM"
        if mode == "DEFENSIVE":
            return "DEFENSIVE / HIGH VOL"
        if scores.macro_risk_score >= 40:
            return "MIXED MACRO ROTATION"
        return "MIXED ROTATION"

    def _decision_signals(
        self,
        mode: str,
        scores: IntelligenceScore,
        critical_count: int,
        high_count: int,
    ) -> list[str]:
        signals: list[str] = []
        if mode == "DEFENSIVE" or critical_count > 0:
            signals.append("DEFENSIVE")
        if mode == "AI_MOMENTUM" or scores.ai_momentum_score >= 45:
            signals.append("RISK-ON")
        if mode == "FCN_RISK" or scores.fcn_risk_score >= 40:
            signals.append("FCN WATCH")
        if mode == "CRYPTO_VOL" or scores.crypto_vol_score >= 40:
            signals.append("VOL EXPANSION")
        if high_count > 0 and len(signals) < 4:
            signals.append("ROTATION")
        return signals[:4] or ["WATCH"]
