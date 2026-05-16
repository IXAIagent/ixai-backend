"""v4A: Portfolio drift engine.

Compares the current snapshot against the last few stored
`intelligence_memory_snapshots` rows (via IntelligenceMemoryStore) and
derives qualitative drift labels per dimension.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.engines.exposure_graph_engine import _float
from app.services.intelligence.persistent_memory import IntelligenceMemoryStore
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    PortfolioDriftSummary,
)


def _direction(delta: float, threshold: float = 8.0) -> str:
    if delta >= threshold:
        return "INCREASING"
    if delta <= -threshold:
        return "DECREASING"
    return "STABLE"


class PortfolioDriftEngine:
    def __init__(self, store: IntelligenceMemoryStore | None = None) -> None:
        self.store = store or IntelligenceMemoryStore()

    def analyse(
        self,
        portfolio_id: str,
        current_concentration: ConcentrationSummary,
        current_regime: str,
        current_volatility_state: str,
        current_fcn_pressure: float,
    ) -> PortfolioDriftSummary:
        try:
            history = self.store.get_recent_history(str(portfolio_id), limit=5)
            window = len(history)
            if window == 0:
                return PortfolioDriftSummary(
                    allocation_drift="UNCHANGED",
                    concentration_drift="UNCHANGED",
                    volatility_drift="UNCHANGED",
                    fcn_pressure_drift="UNCHANGED",
                    regime_drift="UNCHANGED",
                    drift_summary=compliance_filter.sanitize_text(
                        "No drift baseline yet; memory still accumulating."
                    ),
                    history_window=0,
                )

            previous = history[-1]
            prev_conc = _float(previous.get("concentration_score"))
            prev_regime = str(previous.get("regime") or previous.get("workspace_mode") or "")
            prev_volatility = str(previous.get("volatility_state") or "")
            prev_total = _float((previous.get("scores") or {}).get("total_score"))
            prev_fcn_stress = _float((previous.get("scores") or {}).get("fcn_risk_score"))

            concentration_delta = current_concentration.concentration_score - prev_conc
            allocation_delta = (
                current_concentration.single_name_pct
                + current_concentration.theme_pct
                - prev_conc
            )
            current_total = current_concentration.concentration_score
            volatility_drift = (
                "UNCHANGED"
                if not prev_volatility or prev_volatility == current_volatility_state
                else f"{prev_volatility} -> {current_volatility_state}"
            )
            regime_drift = (
                "UNCHANGED"
                if not prev_regime or prev_regime == current_regime
                else f"{prev_regime} -> {current_regime}"
            )
            fcn_drift = _direction(current_fcn_pressure - prev_fcn_stress, threshold=10)

            summary_text = self._summary(
                concentration_delta,
                volatility_drift,
                regime_drift,
                fcn_drift,
                current_total - prev_total,
            )

            return PortfolioDriftSummary(
                allocation_drift=_direction(allocation_delta),
                concentration_drift=_direction(concentration_delta),
                volatility_drift=volatility_drift,
                fcn_pressure_drift=fcn_drift,
                regime_drift=regime_drift,
                drift_summary=compliance_filter.sanitize_text(summary_text, max_length=240),
                history_window=window,
            )
        except Exception:
            return PortfolioDriftSummary(
                drift_summary=compliance_filter.sanitize_text(
                    "Drift engine unavailable; using fail-soft fallback."
                )
            )

    def _summary(
        self,
        concentration_delta: float,
        volatility_drift: str,
        regime_drift: str,
        fcn_drift: str,
        total_delta: float,
    ) -> str:
        parts: list[str] = []
        if regime_drift != "UNCHANGED":
            parts.append(f"Regime: {regime_drift}.")
        if abs(concentration_delta) >= 8:
            parts.append(
                "Concentration "
                + ("rose" if concentration_delta > 0 else "fell")
                + f" by {abs(concentration_delta):.1f} pts."
            )
        if volatility_drift != "UNCHANGED":
            parts.append(f"Volatility state: {volatility_drift}.")
        if fcn_drift != "STABLE":
            parts.append(f"FCN pressure: {fcn_drift.lower()}.")
        if not parts:
            return "Portfolio drift is contained relative to the recent snapshot."
        if abs(total_delta) >= 10:
            parts.append(
                "Total intelligence score moved "
                + ("up" if total_delta > 0 else "down")
                + f" by {abs(total_delta):.0f} pts."
            )
        return " ".join(parts)
