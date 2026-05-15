from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import (
    IntelligenceCorrelation,
    IntelligenceScore,
    LongMemorySummary,
    ReasoningResult,
    ScenarioResult,
    ThemeEvolution,
    WorkspaceDecision,
)
from app.services.news.schemas import NewsArticle


class IntelligenceReasoningEngine:
    def reason(
        self,
        scores: IntelligenceScore,
        scenarios: list[ScenarioResult],
        correlations: list[IntelligenceCorrelation],
        themes: ThemeEvolution,
        workspace: WorkspaceDecision,
        long_memory: LongMemorySummary,
        alerts: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
        portfolio_payload: dict[str, Any],
    ) -> ReasoningResult:
        try:
            top_risks = self._top_risks(scores, scenarios, alerts, fcn_analysis)
            top_strengths = self._top_strengths(scores, themes)
            dependencies = self._dependencies(correlations, themes)
            concentration = self._concentration(portfolio_payload, scores)
            volatility = self._volatility(scores, long_memory)
            why = self._why_workspace(workspace, scores, fcn_analysis)
            changed = self._changed_this_week(long_memory, themes)
            summary = self._summary(workspace, top_risks, top_strengths)
            return ReasoningResult(
                top_risks=compliance_filter.sanitize_list(top_risks),
                top_strengths=compliance_filter.sanitize_list(top_strengths),
                key_dependencies=compliance_filter.sanitize_list(dependencies),
                concentration_analysis=compliance_filter.sanitize_text(concentration),
                volatility_analysis=compliance_filter.sanitize_text(volatility),
                reasoning_summary=compliance_filter.sanitize_text(summary),
                why_workspace_mode=compliance_filter.sanitize_text(why),
                what_changed_this_week=compliance_filter.sanitize_text(changed),
            )
        except Exception:
            return ReasoningResult(reasoning_summary="Reasoning engine 暫時無法完成完整分析，已回到基礎監控。")

    def _top_risks(
        self,
        scores: IntelligenceScore,
        scenarios: list[ScenarioResult],
        alerts: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
    ) -> list[str]:
        risks: list[str] = []
        if scores.fcn_risk_score >= 45:
            risks.append("FCN KI/KO sensitivity is elevated.")
        if scores.crypto_vol_score >= 45:
            risks.append("Crypto volatility can amplify short-term portfolio moves.")
        if scores.macro_risk_score >= 45:
            risks.append("Macro/rates pressure may affect risk asset valuation.")
        if alerts:
            risks.append("High-priority intelligence events are active.")
        if any(str(item.get("risk_level") or "").lower() == "high" for item in fcn_analysis):
            risks.append("At least one FCN monitor item is in high risk state.")
        risks.extend(f"{item.scenario_name}: {item.impact_level}" for item in scenarios if item.impact_level in {"HIGH", "CRITICAL"})
        return risks[:5] or ["No dominant risk cluster detected."]

    def _top_strengths(self, scores: IntelligenceScore, themes: ThemeEvolution) -> list[str]:
        strengths: list[str] = []
        if scores.ai_momentum_score >= 45:
            strengths.append("AI/chip momentum remains a meaningful portfolio theme.")
        if scores.portfolio_relevance_score >= 45:
            strengths.append("Portfolio intelligence relevance is high, improving situational awareness.")
        if themes.dominant_themes:
            strengths.append(f"Dominant themes are identifiable: {', '.join(themes.dominant_themes[:3])}.")
        return strengths[:4] or ["Portfolio signal mix is balanced rather than dominated by one factor."]

    def _dependencies(self, correlations: list[IntelligenceCorrelation], themes: ThemeEvolution) -> list[str]:
        values = [f"{item.source_symbol} depends on {', '.join(item.related_symbols[:3]) or item.correlation_type}" for item in correlations[:4]]
        values.extend(f"Theme dependency: {theme}" for theme in themes.dominant_themes[:2])
        return values[:5] or ["No strong dependency chain detected yet."]

    def _concentration(self, payload: dict[str, Any], scores: IntelligenceScore) -> str:
        total = self._float(payload.get("total_value"))
        if total <= 0:
            return "Portfolio value is not available for concentration analysis."
        top_symbol = "-"
        top_ratio = 0.0
        for position in payload.get("stock_positions", []) + payload.get("crypto_positions", []):
            ratio = self._float(position.get("current_value")) / total
            if ratio > top_ratio:
                top_ratio = ratio
                top_symbol = str(position.get("symbol") or "POSITION")
        if top_ratio >= 0.3:
            return f"{top_symbol} is the largest concentration at roughly {top_ratio:.0%}; monitor single-name sensitivity."
        if scores.ai_momentum_score >= 45:
            return "Concentration is currently more thematic around AI/chip exposure than single-name only."
        return "Concentration profile appears diversified enough for current MVP monitoring."

    def _volatility(self, scores: IntelligenceScore, memory: LongMemorySummary) -> str:
        if scores.crypto_vol_score >= 55 or memory.crypto_vol_trend == "RISING":
            return "Volatility pressure is most visible in crypto-linked signals."
        if scores.macro_risk_score >= 55:
            return "Volatility pressure is likely macro/rates driven."
        return "Volatility pressure is not the dominant portfolio driver right now."

    def _why_workspace(self, workspace: WorkspaceDecision, scores: IntelligenceScore, fcn_analysis: list[dict[str, Any]]) -> str:
        if workspace.workspace_mode == "FCN_RISK":
            worst = next((str(item.get("worst_symbol") or item.get("worst_of") or "") for item in fcn_analysis if item), "")
            return f"Workspace shifted to FCN_RISK because FCN score is {scores.fcn_risk_score:.0f} and worst-of sensitivity is active {worst}."
        if workspace.workspace_mode == "AI_MOMENTUM":
            return f"Workspace shifted to AI_MOMENTUM because AI momentum score is {scores.ai_momentum_score:.0f}."
        if workspace.workspace_mode == "CRYPTO_VOL":
            return f"Workspace shifted to CRYPTO_VOL because crypto volatility score is {scores.crypto_vol_score:.0f}."
        if workspace.workspace_mode == "DEFENSIVE":
            return "Workspace is defensive because total or macro risk score is elevated."
        return "Workspace remains balanced because no single risk cluster dominates."

    def _changed_this_week(self, memory: LongMemorySummary, themes: ThemeEvolution) -> str:
        changes = []
        if memory.historical_risk_trend != "STABLE":
            changes.append(f"Historical risk trend is {memory.historical_risk_trend}.")
        if themes.emerging_themes:
            changes.append(f"Emerging themes: {', '.join(themes.emerging_themes[:3])}.")
        return " ".join(changes) or "This week shows no major directional change in stored intelligence memory."

    def _summary(self, workspace: WorkspaceDecision, risks: list[str], strengths: list[str]) -> str:
        return f"{workspace.workspace_mode} is active. Main risk: {risks[0]} Main support: {strengths[0]}"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
