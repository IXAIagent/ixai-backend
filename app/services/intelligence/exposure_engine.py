from __future__ import annotations

from typing import Any


AI_SYMBOLS = {"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB", "AMD"}
MAG7_SYMBOLS = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA"}
HIGH_BETA_SYMBOLS = {"TSLA", "NVDA", "AMD", "PLTR", "MDB", "MRVL", "COIN", "MSTR"}


class ExposureIntelligenceEngine:
    def analyze(self, portfolio_payload: dict[str, Any], fcn_analysis: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            total = self._float(portfolio_payload.get("total_value"))
            stock_positions = portfolio_payload.get("stock_positions", [])
            crypto_positions = portfolio_payload.get("crypto_positions", [])
            fcn_positions = portfolio_payload.get("fcn_positions", [])

            single = self._single_stock(stock_positions, total)
            ai = self._theme_ratio(stock_positions, total, AI_SYMBOLS)
            mag7 = self._theme_ratio(stock_positions, total, MAG7_SYMBOLS)
            high_beta = self._theme_ratio(stock_positions, total, HIGH_BETA_SYMBOLS)
            crypto = self._value_sum(crypto_positions) / total * 100 if total > 0 else 0
            fcn = self._fcn_correlated_ratio(fcn_positions, total)
            top_correlated = self._top_correlated_symbols(stock_positions, fcn_analysis)
            concentration_score = min(100.0, max(single, ai, crypto, fcn, mag7, high_beta) * 1.35)
            return {
                "single_stock_exposure": round(single, 2),
                "ai_theme_concentration": round(ai, 2),
                "crypto_concentration": round(crypto, 2),
                "fcn_correlated_exposure": round(fcn, 2),
                "magnificent7_concentration": round(mag7, 2),
                "high_beta_concentration": round(high_beta, 2),
                "concentration_score": round(concentration_score, 2),
                "top_correlated_symbols": top_correlated,
                "thematic_exposure_summary": self._summary(ai, crypto, fcn, mag7, high_beta),
            }
        except Exception:
            return {
                "single_stock_exposure": 0,
                "ai_theme_concentration": 0,
                "crypto_concentration": 0,
                "fcn_correlated_exposure": 0,
                "magnificent7_concentration": 0,
                "high_beta_concentration": 0,
                "concentration_score": 0,
                "top_correlated_symbols": [],
                "thematic_exposure_summary": "Exposure intelligence unavailable; using defensive fallback.",
            }

    def _single_stock(self, positions: list[dict[str, Any]], total: float) -> float:
        if total <= 0:
            return 0
        return max((self._float(position.get("current_value")) / total * 100 for position in positions), default=0)

    def _theme_ratio(self, positions: list[dict[str, Any]], total: float, symbols: set[str]) -> float:
        if total <= 0:
            return 0
        value = sum(
            self._float(position.get("current_value"))
            for position in positions
            if str(position.get("symbol") or "").upper() in symbols
        )
        return value / total * 100

    def _value_sum(self, positions: list[dict[str, Any]]) -> float:
        return sum(self._float(position.get("current_value")) for position in positions)

    def _fcn_correlated_ratio(self, positions: list[dict[str, Any]], total: float) -> float:
        if total <= 0:
            return 0
        value = sum(self._float(position.get("notional_amount")) for position in positions)
        return value / total * 100

    def _top_correlated_symbols(self, stocks: list[dict[str, Any]], fcn_analysis: list[dict[str, Any]]) -> list[str]:
        symbols = [str(item.get("worst_symbol") or item.get("worst_of") or "").upper() for item in fcn_analysis]
        symbols.extend(str(item.get("symbol") or "").upper() for item in stocks if str(item.get("symbol") or "").upper() in AI_SYMBOLS)
        return list(dict.fromkeys(symbol for symbol in symbols if symbol))[:8]

    def _summary(self, ai: float, crypto: float, fcn: float, mag7: float, high_beta: float) -> str:
        parts = []
        if ai >= 25:
            parts.append(f"AI theme {ai:.0f}%")
        if crypto >= 10:
            parts.append(f"crypto {crypto:.0f}%")
        if fcn >= 15:
            parts.append(f"FCN-linked {fcn:.0f}%")
        if mag7 >= 25:
            parts.append(f"Mag7 {mag7:.0f}%")
        if high_beta >= 25:
            parts.append(f"high beta {high_beta:.0f}%")
        return " / ".join(parts) if parts else "No dominant thematic concentration detected."

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
