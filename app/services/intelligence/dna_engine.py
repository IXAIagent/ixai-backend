from __future__ import annotations

from typing import Any

from app.services.intelligence.schemas import IntelligenceScore, PortfolioDNA


class PortfolioDNAEngine:
    def analyze(self, portfolio_payload: dict[str, Any], scores: IntelligenceScore) -> PortfolioDNA:
        try:
            total = self._float(portfolio_payload.get("total_value"))
            stock_value = self._float(portfolio_payload.get("stock_value"))
            fcn_value = self._float(portfolio_payload.get("fcn_value"))
            crypto_value = self._float(portfolio_payload.get("crypto_value"))
            cash_value = self._float(portfolio_payload.get("cash_value"))
            fcn_ratio = fcn_value / total if total > 0 else 0
            crypto_ratio = crypto_value / total if total > 0 else 0
            cash_ratio = cash_value / total if total > 0 else 0

            ai_level = self._level(scores.ai_momentum_score)
            fcn_level = self._ratio_level(fcn_ratio)
            crypto_level = self._ratio_level(crypto_ratio)
            dominant_style = self._style(scores, fcn_ratio, crypto_ratio, cash_ratio, stock_value, total)
            return PortfolioDNA(
                dominant_style=dominant_style,
                risk_profile=self._risk_profile(scores.total_score, cash_ratio),
                volatility_profile=self._volatility_profile(scores.crypto_vol_score, scores.macro_risk_score),
                concentration_profile=self._concentration_profile(scores, fcn_ratio, crypto_ratio),
                AI_exposure_level=ai_level,
                FCN_dependency_level=fcn_level,
                crypto_dependency_level=crypto_level,
                macro_sensitivity=self._level(scores.macro_risk_score),
            )
        except Exception:
            return PortfolioDNA()

    def _style(self, scores: IntelligenceScore, fcn_ratio: float, crypto_ratio: float, cash_ratio: float, stock_value: float, total: float) -> str:
        if scores.ai_momentum_score >= 45 and fcn_ratio >= 0.15:
            return "AI Growth + FCN Yield"
        if scores.ai_momentum_score >= 45:
            return "AI Growth"
        if fcn_ratio >= 0.25:
            return "Structured Yield"
        if crypto_ratio >= 0.15:
            return "Crypto Volatility"
        if cash_ratio >= 0.3:
            return "Defensive Cash"
        if total > 0 and stock_value / total >= 0.6:
            return "Equity Core"
        return "Balanced Multi-Asset"

    def _risk_profile(self, total_score: float, cash_ratio: float) -> str:
        if total_score >= 65:
            return "Aggressive / High Monitoring"
        if total_score >= 40:
            return "Moderately Aggressive"
        if cash_ratio >= 0.3:
            return "Defensive"
        return "Balanced"

    def _volatility_profile(self, crypto_score: float, macro_score: float) -> str:
        if crypto_score >= 55:
            return "Crypto-led High Volatility"
        if macro_score >= 55:
            return "Macro-sensitive Volatility"
        return "Moderate"

    def _concentration_profile(self, scores: IntelligenceScore, fcn_ratio: float, crypto_ratio: float) -> str:
        if fcn_ratio >= 0.3:
            return "FCN Concentrated"
        if scores.ai_momentum_score >= 55:
            return "AI/Chip Thematic"
        if crypto_ratio >= 0.2:
            return "Crypto Concentrated"
        return "Diversified"

    def _level(self, score: float) -> str:
        if score >= 60:
            return "HIGH"
        if score >= 35:
            return "MEDIUM"
        return "LOW"

    def _ratio_level(self, ratio: float) -> str:
        if ratio >= 0.25:
            return "HIGH"
        if ratio >= 0.1:
            return "MEDIUM"
        return "LOW"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
