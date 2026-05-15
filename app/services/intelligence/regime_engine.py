from __future__ import annotations

from typing import Any

from app.services.intelligence.schemas import IntelligenceScore
from app.services.news.schemas import NewsArticle


class PortfolioRegimeEngine:
    REGIMES = {
        "RISK_ON",
        "RISK_OFF",
        "AI_MOMENTUM",
        "CRYPTO_SPECULATIVE",
        "DEFENSIVE",
        "HIGH_VOLATILITY",
    }

    def detect(
        self,
        portfolio_payload: dict[str, Any],
        scores: IntelligenceScore,
        articles: list[NewsArticle],
        fcn_analysis: list[dict[str, Any]],
        exposure: dict[str, Any],
    ) -> str:
        try:
            recent_negative = sum(1 for article in articles if str(article.impact or "").lower() == "negative")
            recent_positive = sum(1 for article in articles if str(article.impact or "").lower() == "positive")
            crypto_ratio = self._ratio(portfolio_payload, "crypto_value")
            fcn_ki_close = any(self._ki_pct(item) is not None and self._ki_pct(item) <= 10 for item in fcn_analysis)
            high_vol = scores.crypto_vol_score >= 60 or scores.macro_risk_score >= 60 or exposure.get("high_beta_concentration", 0) >= 35

            if fcn_ki_close or scores.fcn_risk_score >= 60:
                return "DEFENSIVE"
            if high_vol:
                return "HIGH_VOLATILITY"
            if crypto_ratio >= 0.18 or scores.crypto_vol_score >= 50:
                return "CRYPTO_SPECULATIVE"
            if scores.ai_momentum_score >= 55 or exposure.get("ai_theme_concentration", 0) >= 35:
                return "AI_MOMENTUM"
            if recent_negative > recent_positive and scores.total_score >= 45:
                return "RISK_OFF"
            if recent_positive >= recent_negative and scores.ai_momentum_score >= 35:
                return "RISK_ON"
            return "DEFENSIVE"
        except Exception:
            return "DEFENSIVE"

    def _ratio(self, payload: dict[str, Any], key: str) -> float:
        total = self._float(payload.get("total_value"))
        if total <= 0:
            return 0
        return self._float(payload.get(key)) / total

    def _ki_pct(self, item: dict[str, Any]) -> float | None:
        value = item.get("distance_to_KI") or item.get("distance_to_ki") or item.get("distance_to_ki_pct")
        try:
            number = float(value)
            return abs(number) * 100 if abs(number) <= 1 else number
        except (TypeError, ValueError):
            return None

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
