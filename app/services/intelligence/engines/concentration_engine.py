"""v4A: Concentration engine.

Computes single-name, theme, FCN underlying, crypto concentration plus the
cash buffer ratio, and classifies overall concentration risk into:
clear / watch / elevated / critical.
"""

from __future__ import annotations

from typing import Any

from app.services.intelligence.engines.exposure_graph_engine import (
    _float,
    _normalise_symbol,
)
from app.services.intelligence.exposure_engine import (
    AI_SYMBOLS,
    HIGH_BETA_SYMBOLS,
    MAG7_SYMBOLS,
)
from app.services.intelligence.schemas import ConcentrationSummary


THEMES_FOR_CONC = {
    "AI_CHIP": AI_SYMBOLS,
    "MAG7": MAG7_SYMBOLS,
    "HIGH_BETA": HIGH_BETA_SYMBOLS,
}


def _classify(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "elevated"
    if score >= 35:
        return "watch"
    return "clear"


class ConcentrationEngine:
    def analyse(self, context: dict[str, Any]) -> ConcentrationSummary:
        try:
            payload = context.get("portfolio_payload") or {}
            fcn_analysis = context.get("fcn_analysis") or []
            stocks = payload.get("stock_positions") or []
            cryptos = payload.get("crypto_positions") or []
            cash_total = _float(payload.get("cash_value"))
            total = _float(payload.get("total_value")) or 1.0

            single_name = self._single_name(stocks, total)
            theme = self._theme_max(stocks, total)
            fcn_underlying = self._fcn_underlying(fcn_analysis, total)
            crypto = self._crypto(cryptos, total)
            cash_buffer = (cash_total / total) * 100 if total > 0 else 0.0

            # 1.30 multiplier mirrors existing `exposure_engine` aggregation
            # but capped at 100. Cash buffer reduces the score modestly.
            raw_max = max(single_name, theme, fcn_underlying, crypto)
            buffer_penalty = max(0.0, 20.0 - cash_buffer) / 20.0  # 0..1
            score = min(100.0, raw_max * 1.30 * (0.85 + 0.30 * buffer_penalty))

            top_label = self._top_label(single_name, theme, fcn_underlying, crypto)

            return ConcentrationSummary(
                single_name_pct=round(single_name, 2),
                theme_pct=round(theme, 2),
                fcn_underlying_pct=round(fcn_underlying, 2),
                crypto_pct=round(crypto, 2),
                cash_buffer_pct=round(cash_buffer, 2),
                concentration_score=round(score, 2),
                risk_level=_classify(score),
                top_concentration_label=top_label,
            )
        except Exception:
            return ConcentrationSummary()

    def _single_name(self, stocks: list[dict[str, Any]], total: float) -> float:
        if total <= 0 or not stocks:
            return 0.0
        return max(
            (_float(s.get("current_value")) / total * 100 for s in stocks), default=0.0
        )

    def _theme_max(self, stocks: list[dict[str, Any]], total: float) -> float:
        if total <= 0 or not stocks:
            return 0.0
        best = 0.0
        for members in THEMES_FOR_CONC.values():
            theme_value = sum(
                _float(s.get("current_value"))
                for s in stocks
                if _normalise_symbol(s.get("symbol")) in members
            )
            best = max(best, theme_value / total * 100)
        return best

    def _fcn_underlying(self, fcn_analysis: list[dict[str, Any]], total: float) -> float:
        if total <= 0 or not fcn_analysis:
            return 0.0
        counts: dict[str, float] = {}
        for item in fcn_analysis:
            notional = _float(item.get("notional_amount") or item.get("notional"))
            underlyings = item.get("underlyings") or item.get("underlying_results") or []
            if not isinstance(underlyings, list) or not underlyings:
                continue
            per_underlying = notional / len(underlyings) if notional > 0 else 0
            for u in underlyings:
                sym = _normalise_symbol(u.get("symbol") if isinstance(u, dict) else u)
                if not sym:
                    continue
                counts[sym] = counts.get(sym, 0) + per_underlying
        if not counts:
            return 0.0
        return max(counts.values()) / total * 100

    def _crypto(self, cryptos: list[dict[str, Any]], total: float) -> float:
        if total <= 0 or not cryptos:
            return 0.0
        crypto_total = sum(_float(c.get("current_value")) for c in cryptos)
        return crypto_total / total * 100

    def _top_label(
        self,
        single_name: float,
        theme: float,
        fcn_underlying: float,
        crypto: float,
    ) -> str:
        pairs = {
            "single name": single_name,
            "theme cluster": theme,
            "FCN underlying": fcn_underlying,
            "crypto bucket": crypto,
        }
        winner = max(pairs.items(), key=lambda kv: kv[1])
        if winner[1] <= 0:
            return ""
        return winner[0]
