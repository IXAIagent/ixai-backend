"""v4B: Volatility state engine.

Derives per-bucket volatility states from scoring engine outputs and FCN
analysis. Pure heuristic; never raises.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.engines.exposure_graph_engine import _float
from app.services.intelligence.schemas import IntelligenceScore, VolatilityStateSummary


def _band(score: float, *, low: float = 25, normal: float = 45, elevated: float = 65) -> str:
    if score >= elevated:
        return "high"
    if score >= normal:
        return "elevated"
    if score >= low:
        return "normal"
    return "low"


class VolatilityStateEngine:
    def analyse(self, context: dict[str, Any]) -> VolatilityStateSummary:
        try:
            scores: IntelligenceScore | None = context.get("scores")
            fcn_analysis = context.get("fcn_analysis") or []
            data_limited = scores is None

            if data_limited:
                return VolatilityStateSummary(
                    equity_volatility_state="data_limited",
                    crypto_volatility_state="data_limited",
                    fcn_sensitivity_state="data_limited",
                    overall_state="data_limited",
                    data_limited=True,
                )

            equity_state = _band(
                max(
                    _float(getattr(scores, "ai_momentum_score", 0)),
                    _float(getattr(scores, "macro_risk_score", 0)) * 0.7,
                )
            )
            crypto_state = _band(_float(getattr(scores, "crypto_vol_score", 0)))
            fcn_state = self._fcn_sensitivity(fcn_analysis, scores)

            overall = self._overall(equity_state, crypto_state, fcn_state)

            return VolatilityStateSummary(
                equity_volatility_state=equity_state,
                crypto_volatility_state=crypto_state,
                fcn_sensitivity_state=fcn_state,
                overall_state=overall,
                data_limited=False,
            )
        except Exception:
            return VolatilityStateSummary(
                equity_volatility_state="data_limited",
                crypto_volatility_state="data_limited",
                fcn_sensitivity_state="data_limited",
                overall_state="data_limited",
                data_limited=True,
            )

    def _fcn_sensitivity(
        self, fcn_analysis: list[dict[str, Any]], scores: IntelligenceScore
    ) -> str:
        if not fcn_analysis:
            return _band(_float(getattr(scores, "fcn_risk_score", 0)))
        close_ki = 0
        for item in fcn_analysis:
            ki = (
                item.get("distance_to_KI")
                or item.get("distance_to_ki")
                or item.get("distance_to_ki_pct")
            )
            try:
                f = float(ki)
                pct = abs(f) * 100 if abs(f) <= 1 else f
                if pct <= 10:
                    close_ki += 2
                elif pct <= 20:
                    close_ki += 1
            except (TypeError, ValueError):
                continue
        base = _float(getattr(scores, "fcn_risk_score", 0))
        score = min(100.0, base + close_ki * 8.0)
        return _band(score)

    def _overall(self, *states: str) -> str:
        priority = {"data_limited": -1, "low": 0, "normal": 1, "elevated": 2, "high": 3}
        worst = max(states, key=lambda s: priority.get(s, 0))
        return worst
