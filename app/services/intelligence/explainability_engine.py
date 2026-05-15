from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import ExplainabilitySummary
from app.services.news.schemas import NewsArticle


class ExplainabilityEngine:
    def explain(
        self,
        regime: str,
        exposure: dict[str, Any],
        drift: dict[str, str],
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
    ) -> ExplainabilitySummary:
        try:
            dominant_driver = self._dominant_driver(regime, exposure, articles)
            hidden_correlation = self._hidden_correlation(exposure, fcn_analysis)
            systemic = self._systemic_risk(regime, exposure, articles)
            why = self._why_risk_increased(drift, dominant_driver)
            changed = drift.get("drift_summary", "今日變化有限。")
            return ExplainabilitySummary(
                why_risk_increased=compliance_filter.sanitize_text(why),
                what_changed_today=compliance_filter.sanitize_text(changed),
                dominant_driver=compliance_filter.sanitize_text(dominant_driver),
                hidden_correlation=compliance_filter.sanitize_text(hidden_correlation),
                systemic_risk=compliance_filter.sanitize_text(systemic),
            )
        except Exception:
            return ExplainabilitySummary(
                why_risk_increased="目前解釋層資料不足，維持風險觀察。",
                what_changed_today="今日未偵測到可解釋的重大變化。",
            )

    def _dominant_driver(self, regime: str, exposure: dict[str, Any], articles: list[NewsArticle]) -> str:
        if regime == "AI_MOMENTUM":
            return "AI/chip theme is the dominant driver."
        if regime == "CRYPTO_SPECULATIVE":
            return "Crypto exposure and volatility are the dominant driver."
        if regime in {"HIGH_VOLATILITY", "RISK_OFF"}:
            return "Negative news tone and high volatility are the dominant driver."
        if self._float(exposure.get("fcn_correlated_exposure")) >= 20:
            return "FCN correlated exposure is the dominant driver."
        if any(article.is_fcn_related for article in articles):
            return "FCN-related news flow is the dominant driver."
        return "Portfolio risk is currently driven by mixed exposure and news tone."

    def _hidden_correlation(self, exposure: dict[str, Any], fcn_analysis: list[dict[str, Any]]) -> str:
        symbols = exposure.get("top_correlated_symbols") or []
        if symbols:
            return f"Hidden correlation appears around {', '.join(symbols[:4])}."
        worst = [str(item.get("worst_symbol") or item.get("worst_of") or "") for item in fcn_analysis if item]
        if worst:
            return f"FCN worst-of symbols may create hidden correlation around {', '.join(worst[:3])}."
        return "No strong hidden correlation detected."

    def _systemic_risk(self, regime: str, exposure: dict[str, Any], articles: list[NewsArticle]) -> str:
        if regime in {"RISK_OFF", "HIGH_VOLATILITY"}:
            return "Systemic risk is tied to broad volatility and negative tone."
        if any("fed" in str(article.title or "").lower() or "cpi" in str(article.title or "").lower() for article in articles):
            return "Macro/rates headlines may become a systemic risk channel."
        if self._float(exposure.get("magnificent7_concentration")) >= 25:
            return "Large-cap technology concentration can become a systemic portfolio risk channel."
        return "Systemic risk is not the dominant driver in the current snapshot."

    def _why_risk_increased(self, drift: dict[str, str], driver: str) -> str:
        if drift.get("exposure_drift") == "INCREASING":
            return f"Risk increased because concentration exposure is rising. {driver}"
        if "→" in drift.get("regime_drift", ""):
            return f"Risk changed because regime shifted. {driver}"
        if drift.get("volatility_drift") not in {"UNCHANGED", "UNKNOWN"}:
            return f"Risk changed because volatility state moved. {driver}"
        return f"Risk has not materially increased; current driver: {driver}"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
