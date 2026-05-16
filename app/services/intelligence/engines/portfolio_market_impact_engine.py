"""v4B: Portfolio market impact engine.

Maps the current market regime / volatility / macro pressure onto the
user's specific portfolio buckets (FCN / crypto / equity / cash) and emits
a per-bucket interpretation. Output is observation-only.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.engines.exposure_graph_engine import _float
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    FCNSystemicRiskSummary,
    MacroNewsRiskSummary,
    MarketRegimeSummary,
    PortfolioMarketImpactSummary,
    VolatilityStateSummary,
)


def _classify(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 50:
        return "elevated"
    if score >= 30:
        return "watch"
    return "clear"


class PortfolioMarketImpactEngine:
    def analyse(
        self,
        context: dict[str, Any],
        concentration: ConcentrationSummary,
        fcn_risk: FCNSystemicRiskSummary,
        regime: MarketRegimeSummary,
        volatility: VolatilityStateSummary,
        macro: MacroNewsRiskSummary,
    ) -> PortfolioMarketImpactSummary:
        try:
            payload = context.get("portfolio_payload") or {}
            total = _float(payload.get("total_value")) or 1.0
            fcn_ratio = _float(payload.get("fcn_value")) / total
            crypto_ratio = _float(payload.get("crypto_value")) / total
            stock_ratio = _float(payload.get("stock_value")) / total
            cash_ratio = _float(payload.get("cash_value")) / total

            fcn_impact = self._fcn(fcn_ratio, fcn_risk, regime, macro)
            crypto_impact = self._crypto(crypto_ratio, volatility, macro)
            equity_impact = self._equity(stock_ratio, concentration, regime, macro, volatility)
            cash_interp = self._cash(cash_ratio)

            severity_score = max(
                self._severity_of(fcn_risk.risk_level),
                self._severity_of(concentration.risk_level),
                40 if volatility.overall_state == "high" else 0,
                20 if volatility.overall_state == "elevated" else 0,
                15 if regime.regime in {"risk_off", "high_volatility", "crypto_stress"} else 0,
            )

            return PortfolioMarketImpactSummary(
                fcn_impact=compliance_filter.sanitize_text(fcn_impact, max_length=220),
                crypto_impact=compliance_filter.sanitize_text(crypto_impact, max_length=220),
                equity_impact=compliance_filter.sanitize_text(equity_impact, max_length=220),
                cash_buffer_interpretation=compliance_filter.sanitize_text(
                    cash_interp, max_length=220
                ),
                overall_impact_level=_classify(severity_score),
            )
        except Exception:
            return PortfolioMarketImpactSummary(
                fcn_impact=compliance_filter.sanitize_text(
                    "FCN market impact unavailable; fail-soft fallback in effect."
                ),
                crypto_impact="",
                equity_impact="",
                cash_buffer_interpretation="",
                overall_impact_level="clear",
            )

    def _severity_of(self, label: str) -> float:
        return {"critical": 90, "elevated": 65, "watch": 40, "clear": 10}.get(label, 0)

    def _fcn(
        self,
        ratio: float,
        fcn_risk: FCNSystemicRiskSummary,
        regime: MarketRegimeSummary,
        macro: MacroNewsRiskSummary,
    ) -> str:
        if ratio <= 0:
            return "No FCN positions; market impact limited to other buckets."
        pieces: list[str] = []
        if fcn_risk.nearest_ki_pct is not None and fcn_risk.nearest_ki_pct <= 10:
            pieces.append("nearest KI is close")
        if fcn_risk.repeated_underlyings:
            pieces.append(
                "repeated underlyings ("
                + ", ".join(fcn_risk.repeated_underlyings[:3])
                + ")"
            )
        if macro.ai_pressure >= 40:
            pieces.append("AI/chip news pressure")
        if regime.regime in {"defensive", "high_volatility", "risk_off"}:
            pieces.append(f"market regime is {regime.regime}")
        if not pieces:
            return "FCN positions face routine monitoring under current market state."
        return "FCN positions are sensitive because " + ", ".join(pieces) + "."

    def _crypto(
        self,
        ratio: float,
        volatility: VolatilityStateSummary,
        macro: MacroNewsRiskSummary,
    ) -> str:
        if ratio <= 0:
            return "No crypto positions; crypto channel impact is limited."
        if volatility.crypto_volatility_state in {"high", "elevated"}:
            return (
                f"Crypto bucket weighting is {ratio * 100:.1f}% and crypto volatility "
                f"state is {volatility.crypto_volatility_state}."
            )
        if macro.crypto_pressure >= 40:
            return "Crypto news pressure is elevated; monitor exchange or leverage related items."
        return f"Crypto bucket weighting is {ratio * 100:.1f}%; impact moderate at current state."

    def _equity(
        self,
        ratio: float,
        concentration: ConcentrationSummary,
        regime: MarketRegimeSummary,
        macro: MacroNewsRiskSummary,
        volatility: VolatilityStateSummary,
    ) -> str:
        if ratio <= 0:
            return "No equity positions; equity channel impact is limited."
        pieces: list[str] = []
        if concentration.risk_level in {"elevated", "critical"}:
            pieces.append(f"concentration {concentration.risk_level}")
        if regime.regime == "ai_momentum" and macro.ai_pressure >= 30:
            pieces.append("AI/chip leadership and news flow may amplify moves")
        if volatility.equity_volatility_state in {"high", "elevated"}:
            pieces.append(f"equity volatility state {volatility.equity_volatility_state}")
        if not pieces:
            return "Equity bucket impact appears moderate under current state."
        return "Equity bucket is sensitive: " + ", ".join(pieces) + "."

    def _cash(self, ratio: float) -> str:
        pct = ratio * 100
        if pct >= 20:
            return f"Cash buffer is {pct:.1f}% — provides flexibility to absorb shocks."
        if pct >= 8:
            return f"Cash buffer is {pct:.1f}% — moderate; continue to monitor allocation balance."
        return f"Cash buffer is only {pct:.1f}% — limited absorptive capacity if volatility rises."
