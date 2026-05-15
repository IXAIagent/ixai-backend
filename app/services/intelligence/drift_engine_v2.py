from __future__ import annotations

from typing import Any


class DriftDetectionV2Engine:
    def detect(
        self,
        current_regime: str,
        exposure: dict[str, Any],
        current_narrative: str,
        history: list[dict[str, Any]],
    ) -> dict[str, str]:
        try:
            previous = history[-1] if history else {}
            previous_regime = str(previous.get("regime") or previous.get("workspace_mode") or "")
            previous_exposure = self._float(previous.get("concentration_score"))
            current_exposure = self._float(exposure.get("concentration_score"))
            previous_vol = str(previous.get("volatility_state") or "")
            current_vol = self._volatility_state(exposure)
            previous_narrative = str((previous.get("narrative") or {}).get("risk_narrative") or "")

            regime_drift = "UNCHANGED" if not previous_regime or previous_regime == current_regime else f"{previous_regime} → {current_regime}"
            exposure_drift = self._direction(current_exposure - previous_exposure)
            volatility_drift = "UNCHANGED" if previous_vol == current_vol or not previous_vol else f"{previous_vol} → {current_vol}"
            narrative_drift = self._narrative_drift(previous_narrative, current_narrative)
            summary = self._summary(regime_drift, exposure_drift, volatility_drift, exposure)
            return {
                "regime_drift": regime_drift,
                "exposure_drift": exposure_drift,
                "volatility_drift": volatility_drift,
                "narrative_drift": narrative_drift,
                "drift_summary": summary,
                "volatility_state": current_vol,
            }
        except Exception:
            return {
                "regime_drift": "UNKNOWN",
                "exposure_drift": "UNKNOWN",
                "volatility_drift": "UNKNOWN",
                "narrative_drift": "UNKNOWN",
                "drift_summary": "Drift detection unavailable; using fail-soft fallback.",
                "volatility_state": "UNKNOWN",
            }

    def _volatility_state(self, exposure: dict[str, Any]) -> str:
        if self._float(exposure.get("crypto_concentration")) >= 15 or self._float(exposure.get("high_beta_concentration")) >= 35:
            return "HIGH_VOL"
        if self._float(exposure.get("concentration_score")) >= 45:
            return "ELEVATED"
        return "NORMAL"

    def _direction(self, delta: float) -> str:
        if delta >= 8:
            return "INCREASING"
        if delta <= -8:
            return "DECREASING"
        return "STABLE"

    def _narrative_drift(self, previous: str, current: str) -> str:
        if not previous:
            return "FIRST_SNAPSHOT"
        previous_keywords = set(previous.lower().split())
        current_keywords = set(current.lower().split())
        overlap = len(previous_keywords & current_keywords)
        if overlap < max(2, min(len(previous_keywords), len(current_keywords)) // 4):
            return "SHIFTING"
        return "STABLE"

    def _summary(self, regime: str, exposure: str, volatility: str, exposure_data: dict[str, Any]) -> str:
        if "→" in regime:
            return f"你的風險狀態正在從 {regime} 漂移，主要暴露為 {exposure_data.get('thematic_exposure_summary')}。"
        if exposure == "INCREASING":
            return f"你的風險正在因 concentration score 上升而增加，主要暴露為 {exposure_data.get('thematic_exposure_summary')}。"
        if volatility != "UNCHANGED":
            return f"你的波動狀態正在變化：{volatility}。"
        return "目前 regime、暴露與敘事變化相對穩定。"

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
