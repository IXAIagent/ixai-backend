"""v4A: Unified intelligence score aggregator.

Combines outputs of the other v4A engines into a single
`UnifiedIntelligenceScore` with a discrete risk_state band.
"""

from __future__ import annotations

from app.services.intelligence.engines.exposure_graph_engine import _float
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    ExposureGraphSummary,
    FCNSystemicRiskSummary,
    PortfolioDriftSummary,
    UnifiedIntelligenceScore,
)
from app.services.intelligence.schemas import IntelligenceScore


def _band(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "elevated"
    if score >= 35:
        return "watch"
    return "clear"


class IntelligenceScoreEngine:
    def aggregate(
        self,
        scores: IntelligenceScore | None,
        exposure: ExposureGraphSummary,
        concentration: ConcentrationSummary,
        fcn_risk: FCNSystemicRiskSummary,
        drift: PortfolioDriftSummary,
        volatility_score: float,
    ) -> UnifiedIntelligenceScore:
        try:
            exposure_score = self._exposure_score(exposure, concentration)
            conc_score = concentration.concentration_score
            fcn_stress = self._fcn_stress_score(fcn_risk, scores)
            drift_score = self._drift_score(drift)
            systemic_score = max(
                conc_score * 0.55 + fcn_stress * 0.45,
                exposure_score * 0.40 + fcn_stress * 0.60,
            )

            total = round(
                min(
                    100.0,
                    0.18 * exposure_score
                    + 0.22 * conc_score
                    + 0.22 * fcn_stress
                    + 0.13 * volatility_score
                    + 0.12 * drift_score
                    + 0.13 * systemic_score,
                ),
                2,
            )

            # Confidence boosts with drift history and lowers when most signals
            # are zero (cold-start portfolios).
            history_weight = min(1.0, drift.history_window / 5.0)
            non_zero_signals = sum(
                1
                for v in (exposure_score, conc_score, fcn_stress, volatility_score)
                if v > 5.0
            )
            confidence = round(
                min(95.0, 30.0 + 40.0 * history_weight + 8.0 * non_zero_signals),
                2,
            )

            return UnifiedIntelligenceScore(
                exposure_score=round(exposure_score, 2),
                concentration_score=round(conc_score, 2),
                fcn_stress_score=round(fcn_stress, 2),
                volatility_score=round(volatility_score, 2),
                drift_score=round(drift_score, 2),
                systemic_score=round(systemic_score, 2),
                total_intelligence_score=total,
                risk_state=_band(total),
                confidence=confidence,
            )
        except Exception:
            return UnifiedIntelligenceScore()

    def _exposure_score(
        self, exposure: ExposureGraphSummary, concentration: ConcentrationSummary
    ) -> float:
        # Heavier when many themes dominate or when high beta / fcn linkage stack.
        score = 0.0
        score += min(40.0, len(exposure.dominant_themes) * 14.0)
        score += min(25.0, len(exposure.high_beta_symbols) * 4.0)
        score += min(20.0, len(exposure.fcn_linked_symbols) * 3.0)
        score += min(15.0, concentration.theme_pct / 100 * 50.0)
        return min(100.0, score)

    def _fcn_stress_score(
        self,
        fcn_risk: FCNSystemicRiskSummary,
        scores: IntelligenceScore | None,
    ) -> float:
        base = _float(getattr(scores, "fcn_risk_score", 0)) if scores else 0
        if fcn_risk.risk_level == "critical":
            return max(base, 90.0)
        if fcn_risk.risk_level == "elevated":
            return max(base, 70.0)
        if fcn_risk.risk_level == "watch":
            return max(base, 45.0)
        return base

    def _drift_score(self, drift: PortfolioDriftSummary) -> float:
        score = 0.0
        if drift.concentration_drift == "INCREASING":
            score += 25
        if drift.concentration_drift == "DECREASING":
            score -= 10
        if drift.fcn_pressure_drift == "INCREASING":
            score += 30
        if drift.volatility_drift not in {"UNCHANGED", "STABLE"}:
            score += 15
        if drift.regime_drift not in {"UNCHANGED", "STABLE"}:
            score += 15
        if drift.history_window == 0:
            return 0.0
        return max(0.0, min(100.0, score + 30.0))  # baseline 30 so non-zero history shows up
