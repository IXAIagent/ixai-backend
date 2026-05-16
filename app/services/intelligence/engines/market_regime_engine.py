"""v4B: Market regime engine (broader than the v2A portfolio regime engine).

Classifies the market state into a single regime label with drivers + a
compliance-safe narrative.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.engines.exposure_graph_engine import _float
from app.services.intelligence.schemas import IntelligenceScore, MarketRegimeSummary


def _impact_counts(articles: list[Any]) -> tuple[int, int]:
    negative = 0
    positive = 0
    for article in articles or []:
        impact = str(getattr(article, "impact", "") or "").lower()
        if impact == "negative":
            negative += 1
        elif impact == "positive":
            positive += 1
    return negative, positive


class MarketRegimeEngine:
    SUPPORTED = (
        "risk_on",
        "risk_off",
        "high_volatility",
        "crypto_stress",
        "ai_momentum",
        "defensive",
        "data_limited",
    )

    def analyse(self, context: dict[str, Any]) -> MarketRegimeSummary:
        try:
            scores: IntelligenceScore = context.get("scores")
            articles = context.get("articles") or []
            fcn_analysis = context.get("fcn_analysis") or []

            if not scores or not articles:
                return MarketRegimeSummary(
                    regime="data_limited",
                    confidence=20.0,
                    drivers=["insufficient data"],
                    narrative=compliance_filter.sanitize_text(
                        "Insufficient news / scoring context to classify market regime; "
                        "fallback to data_limited."
                    ),
                )

            negative, positive = _impact_counts(articles)
            ki_close = any(
                self._ki_pct(item) is not None and (self._ki_pct(item) or 100) <= 10
                for item in fcn_analysis
            )
            high_vol = (
                _float(scores.crypto_vol_score) >= 60
                or _float(scores.macro_risk_score) >= 60
            )

            drivers: list[str] = []
            if ki_close:
                drivers.append("FCN KI proximity")
            if high_vol:
                drivers.append("volatility scores elevated")
            if _float(scores.ai_momentum_score) >= 55:
                drivers.append("AI momentum elevated")
            if _float(scores.crypto_vol_score) >= 50:
                drivers.append("crypto pressure")
            if negative > positive:
                drivers.append("news tone negative")
            elif positive > negative:
                drivers.append("news tone positive")

            if ki_close or _float(scores.fcn_risk_score) >= 60:
                regime = "defensive"
            elif _float(scores.crypto_vol_score) >= 65:
                regime = "crypto_stress"
            elif high_vol:
                regime = "high_volatility"
            elif _float(scores.ai_momentum_score) >= 55:
                regime = "ai_momentum"
            elif negative > positive and _float(scores.total_score) >= 45:
                regime = "risk_off"
            elif positive >= negative and _float(scores.ai_momentum_score) >= 35:
                regime = "risk_on"
            else:
                regime = "defensive"

            confidence = min(
                90.0,
                40.0
                + min(40.0, len(drivers) * 10.0)
                + (10.0 if _float(scores.total_score) >= 50 else 0.0),
            )

            narrative = compliance_filter.sanitize_text(
                self._narrative(regime, drivers),
                max_length=220,
            )

            return MarketRegimeSummary(
                regime=regime,
                confidence=round(confidence, 2),
                drivers=drivers[:4] or ["mixed signals"],
                narrative=narrative,
            )
        except Exception:
            return MarketRegimeSummary(
                regime="data_limited",
                confidence=0.0,
                drivers=["engine error"],
                narrative=compliance_filter.sanitize_text(
                    "Market regime engine unavailable; using fail-soft fallback."
                ),
            )

    def _ki_pct(self, item: dict[str, Any]) -> float | None:
        value = (
            item.get("distance_to_KI")
            or item.get("distance_to_ki")
            or item.get("distance_to_ki_pct")
        )
        if value is None:
            return None
        try:
            f = float(value)
            return abs(f) * 100 if abs(f) <= 1 else f
        except (TypeError, ValueError):
            return None

    def _narrative(self, regime: str, drivers: list[str]) -> str:
        driver_text = ", ".join(drivers[:3]) if drivers else "limited signals"
        if regime == "defensive":
            return f"Market reads defensive (drivers: {driver_text}). Continue to monitor."
        if regime == "risk_off":
            return f"Market tilt risk-off (drivers: {driver_text})."
        if regime == "risk_on":
            return f"Market tilt risk-on (drivers: {driver_text})."
        if regime == "high_volatility":
            return f"Volatility regime active (drivers: {driver_text})."
        if regime == "crypto_stress":
            return f"Crypto stress dominates (drivers: {driver_text})."
        if regime == "ai_momentum":
            return f"AI / chip theme leads (drivers: {driver_text})."
        return "Insufficient data to classify the market regime confidently."
