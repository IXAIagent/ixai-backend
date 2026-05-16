"""v4A: FCN systemic risk engine.

Aggregates worst-of pressure, nearest KI distance, repeated underlyings,
and KI cluster detection across all FCNs in the portfolio.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.intelligence.engines.exposure_graph_engine import (
    _float,
    _normalise_symbol,
)
from app.services.intelligence.schemas import FCNSystemicRiskSummary


def _ki_distance_pct(value: Any) -> float | None:
    raw = _float(value, fallback=float("nan"))
    if raw != raw:  # NaN check
        return None
    return abs(raw) * 100 if abs(raw) <= 1 else raw


class FCNSystemicRiskEngine:
    def analyse(self, context: dict[str, Any]) -> FCNSystemicRiskSummary:
        try:
            fcn_analysis = context.get("fcn_analysis") or []
            if not fcn_analysis:
                return FCNSystemicRiskSummary(
                    observation_clustering="unknown", risk_level="clear"
                )

            worst_pressures: list[float] = []
            ki_values: list[tuple[str, float]] = []
            underlying_counts: Counter[str] = Counter()
            observation_dates: list[str] = []

            for item in fcn_analysis:
                worst_pressure = _float(
                    item.get("worst_performance")
                    or item.get("worst_of_performance")
                    or 0
                )
                # negative = drawdown vs initial; convert to positive pressure pct
                if worst_pressure < 0:
                    worst_pressures.append(abs(worst_pressure) * 100 if abs(worst_pressure) <= 1 else abs(worst_pressure))
                ki = _ki_distance_pct(
                    item.get("distance_to_KI")
                    or item.get("distance_to_ki")
                    or item.get("distance_to_ki_pct")
                )
                code = _normalise_symbol(
                    item.get("fcn_code") or item.get("name") or item.get("code") or "FCN"
                )
                if ki is not None:
                    ki_values.append((code, ki))

                underlyings = item.get("underlyings") or item.get("underlying_results") or []
                if isinstance(underlyings, list):
                    for u in underlyings:
                        sym = _normalise_symbol(u.get("symbol") if isinstance(u, dict) else u)
                        if sym:
                            underlying_counts[sym] += 1

                obs = item.get("next_observation_date") or item.get("observation_dates")
                if isinstance(obs, str) and obs.strip():
                    observation_dates.append(obs.strip()[:10])

            worst_pressure = max(worst_pressures) if worst_pressures else 0.0
            nearest = (
                min(ki for _, ki in ki_values) if ki_values else None
            )
            ki_cluster = sorted(
                code for code, ki in ki_values if ki is not None and ki <= 15
            )
            repeated = sorted(
                sym for sym, count in underlying_counts.items() if count >= 2
            )

            clustering = self._observation_clustering(observation_dates)
            level = self._classify(worst_pressure, nearest, len(repeated), len(ki_cluster))

            return FCNSystemicRiskSummary(
                worst_of_pressure_pct=round(worst_pressure, 2),
                nearest_ki_pct=None if nearest is None else round(nearest, 2),
                repeated_underlyings=repeated,
                ki_cluster_symbols=ki_cluster,
                observation_clustering=clustering,
                risk_level=level,
            )
        except Exception:
            return FCNSystemicRiskSummary(observation_clustering="unknown")

    def _classify(
        self,
        worst_pressure: float,
        nearest_ki: float | None,
        repeated_count: int,
        cluster_count: int,
    ) -> str:
        if nearest_ki is not None and nearest_ki <= 5:
            return "critical"
        if cluster_count >= 3 or repeated_count >= 3 or worst_pressure >= 25:
            return "elevated"
        if (nearest_ki is not None and nearest_ki <= 15) or worst_pressure >= 10 or repeated_count >= 1:
            return "watch"
        return "clear"

    def _observation_clustering(self, dates: list[str]) -> str:
        if not dates:
            return "unknown"
        unique = set(dates)
        # If >=3 FCNs share an observation date within the captured window,
        # surface as clustered. Otherwise spread.
        counts = Counter(dates)
        if any(count >= 3 for count in counts.values()):
            return "clustered"
        if len(unique) >= 2:
            return "spread"
        return "spread"
