from __future__ import annotations

from typing import Any

from app.services.intelligence.compliance import compliance_filter
from app.services.intelligence.schemas import IntelligenceCorrelation, IntelligenceScore, ScenarioResult


class ScenarioEngine:
    def build_scenarios(
        self,
        portfolio_payload: dict[str, Any],
        scores: IntelligenceScore,
        correlations: list[IntelligenceCorrelation],
        fcn_analysis: list[dict[str, Any]],
    ) -> list[ScenarioResult]:
        try:
            scenarios = [
                self._btc_drop(portfolio_payload, scores),
                self._nvda_miss(portfolio_payload, scores),
                self._fcn_worst_drop(fcn_analysis, scores),
                self._rate_hike(scores, correlations),
                self._ai_pullback(portfolio_payload, scores),
            ]
            return [self._sanitize(item) for item in scenarios]
        except Exception:
            return []

    def _btc_drop(self, payload: dict[str, Any], scores: IntelligenceScore) -> ScenarioResult:
        affected = self._symbols(payload.get("crypto_positions", []), fallback=["BTC"])
        level = "HIGH" if scores.crypto_vol_score >= 55 else "MEDIUM" if affected else "LOW"
        return ScenarioResult(
            scenario_name="BTC_DROP_10",
            impact_level=level,
            affected_assets=affected,
            portfolio_sensitivity="Crypto exposure and leverage can amplify short-term portfolio volatility.",
            fcn_risk_change="No direct FCN change unless BTC is an underlying.",
            narrative="若 BTC 快速下跌 10%，crypto 曝險可能放大短期淨值波動，需觀察槓桿與流動性風險。",
        )

    def _nvda_miss(self, payload: dict[str, Any], scores: IntelligenceScore) -> ScenarioResult:
        affected = self._symbols(payload.get("stock_positions", []), include={"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB"})
        level = "HIGH" if scores.ai_momentum_score >= 55 else "MEDIUM" if affected else "LOW"
        return ScenarioResult(
            scenario_name="NVDA_EARNINGS_MISS",
            impact_level=level,
            affected_assets=affected or ["AI/CHIP"],
            portfolio_sensitivity="AI/chip concentration may raise sensitivity to earnings disappointment.",
            fcn_risk_change="If AI/chip names are FCN underlyings, KI distance may become more sensitive.",
            narrative="若 AI 龍頭財報不如預期，半導體與 AI infrastructure 情緒可能轉弱，相關持倉與 FCN underlying 需提高觀察。",
        )

    def _fcn_worst_drop(self, fcn_analysis: list[dict[str, Any]], scores: IntelligenceScore) -> ScenarioResult:
        affected = [
            str(item.get("worst_symbol") or item.get("worst_of") or "FCN")
            for item in fcn_analysis[:5]
        ] or ["FCN"]
        level = "HIGH" if scores.fcn_risk_score >= 55 else "MEDIUM" if fcn_analysis else "LOW"
        return ScenarioResult(
            scenario_name="FCN_WORST_OF_DROP",
            impact_level=level,
            affected_assets=affected,
            portfolio_sensitivity="Worst-of decline can increase structured product knock-in sensitivity.",
            fcn_risk_change="KI distance may tighten if worst-of underlying falls further.",
            narrative="若 FCN worst-of 標的續跌，KI/KO 安全距離可能收斂，需觀察 worst-of 價格與下一觀察日。",
        )

    def _rate_hike(self, scores: IntelligenceScore, correlations: list[IntelligenceCorrelation]) -> ScenarioResult:
        affected = sorted({symbol for item in correlations for symbol in item.related_symbols})[:6]
        level = "HIGH" if scores.macro_risk_score >= 55 else "MEDIUM"
        return ScenarioResult(
            scenario_name="RATE_HIKE_SHOCK",
            impact_level=level,
            affected_assets=affected or ["Macro-sensitive assets"],
            portfolio_sensitivity="Higher-rate shock can pressure long-duration growth assets and risk appetite.",
            fcn_risk_change="Rate shock may indirectly pressure FCN underlyings through equity volatility.",
            narrative="若利率或通膨衝擊升溫，成長股與高波動資產可能承壓，需觀察宏觀風險是否擴散至持倉。",
        )

    def _ai_pullback(self, payload: dict[str, Any], scores: IntelligenceScore) -> ScenarioResult:
        affected = self._symbols(payload.get("stock_positions", []), include={"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB"})
        level = "HIGH" if scores.ai_momentum_score >= 55 else "MEDIUM" if affected else "LOW"
        return ScenarioResult(
            scenario_name="AI_SECTOR_PULLBACK",
            impact_level=level,
            affected_assets=affected or ["AI/CHIP"],
            portfolio_sensitivity="AI/chip pullback can affect concentrated technology exposure.",
            fcn_risk_change="AI/chip underlyings in FCN may see tighter KI distance under pullback.",
            narrative="若 AI 類股出現回檔，組合中的科技集中度與 FCN underlying 敏感度可能同步升高。",
        )

    def _symbols(self, positions: list[dict[str, Any]], include: set[str] | None = None, fallback: list[str] | None = None) -> list[str]:
        symbols = []
        for position in positions:
            symbol = str(position.get("symbol") or "").upper()
            if symbol and (include is None or symbol in include):
                symbols.append(symbol)
        return symbols[:8] or (fallback or [])

    def _sanitize(self, scenario: ScenarioResult) -> ScenarioResult:
        scenario.portfolio_sensitivity = compliance_filter.sanitize_text(scenario.portfolio_sensitivity)
        scenario.fcn_risk_change = compliance_filter.sanitize_text(scenario.fcn_risk_change)
        scenario.narrative = compliance_filter.sanitize_text(scenario.narrative, max_length=160)
        return scenario
