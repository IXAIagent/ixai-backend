"""v4A: Exposure graph engine.

Builds an asset → theme → risk-factor graph from a portfolio payload plus
FCN underlying parsing. Output is structured (nodes + edges) so the
frontend can render without rebuilding the same logic.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.intelligence.exposure_engine import (
    AI_SYMBOLS,
    HIGH_BETA_SYMBOLS,
    MAG7_SYMBOLS,
)
from app.services.intelligence.schemas import (
    ExposureGraphEdge,
    ExposureGraphNode,
    ExposureGraphSummary,
)


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value if value is not None else fallback)
    except (TypeError, ValueError):
        return fallback


def _normalise_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


class ExposureGraphEngine:
    THEMES = {
        "AI_CHIP": AI_SYMBOLS,
        "MAG7": MAG7_SYMBOLS,
        "HIGH_BETA": HIGH_BETA_SYMBOLS,
    }

    RISK_FACTORS = {
        "AI_CHIP": ["AI_THEME_RISK", "TECH_CONCENTRATION_RISK"],
        "MAG7": ["MEGA_CAP_CONCENTRATION_RISK"],
        "HIGH_BETA": ["VOLATILITY_RISK"],
        "CRYPTO": ["CRYPTO_VOLATILITY_RISK"],
        "FCN_UNDERLYING": ["FCN_KI_RISK"],
    }

    def analyse(self, context: dict[str, Any]) -> ExposureGraphSummary:
        try:
            payload = context.get("portfolio_payload") or {}
            fcn_analysis = context.get("fcn_analysis") or []
            stocks = payload.get("stock_positions") or []
            cryptos = payload.get("crypto_positions") or []
            total = _float(payload.get("total_value")) or 1.0

            nodes: dict[str, ExposureGraphNode] = {}
            edges: list[ExposureGraphEdge] = []
            theme_weights: Counter[str] = Counter()
            high_beta_symbols: set[str] = set()
            fcn_linked_symbols: set[str] = set()

            def add_node(label: str, node_type: str, weight: float = 0.0) -> None:
                if not label:
                    return
                existing = nodes.get(label)
                if existing:
                    existing.weight = round(max(existing.weight, weight), 2)
                else:
                    nodes[label] = ExposureGraphNode(
                        label=label, node_type=node_type, weight=round(weight, 2)
                    )

            for stock in stocks:
                symbol = _normalise_symbol(stock.get("symbol"))
                if not symbol:
                    continue
                weight = (_float(stock.get("current_value")) / total) * 100
                add_node(symbol, "asset", weight)
                for theme, members in self.THEMES.items():
                    if symbol in members:
                        add_node(theme, "theme")
                        edges.append(
                            ExposureGraphEdge(
                                source=symbol,
                                target=theme,
                                edge_type="asset_in_theme",
                                weight=round(weight, 2),
                            )
                        )
                        theme_weights[theme] += weight
                        if theme == "HIGH_BETA":
                            high_beta_symbols.add(symbol)

            for crypto in cryptos:
                symbol = _normalise_symbol(crypto.get("symbol"))
                if not symbol:
                    continue
                weight = (_float(crypto.get("current_value")) / total) * 100
                add_node(symbol, "asset", weight)
                add_node("CRYPTO", "theme")
                edges.append(
                    ExposureGraphEdge(
                        source=symbol,
                        target="CRYPTO",
                        edge_type="asset_in_theme",
                        weight=round(weight, 2),
                    )
                )
                theme_weights["CRYPTO"] += weight

            # FCN underlyings → repeated detection + theme attachment
            underlying_counts: Counter[str] = Counter()
            for item in fcn_analysis:
                fcn_code = _normalise_symbol(
                    item.get("fcn_code") or item.get("name") or "FCN"
                )
                add_node(fcn_code, "asset")
                underlyings = item.get("underlyings") or item.get("underlying_results") or []
                if isinstance(underlyings, list):
                    for underlying in underlyings:
                        if isinstance(underlying, dict):
                            sym = _normalise_symbol(underlying.get("symbol"))
                        else:
                            sym = _normalise_symbol(underlying)
                        if not sym:
                            continue
                        underlying_counts[sym] += 1
                        fcn_linked_symbols.add(sym)
                        add_node(sym, "asset")
                        edges.append(
                            ExposureGraphEdge(
                                source=fcn_code,
                                target=sym,
                                edge_type="fcn_underlying",
                                weight=1,
                            )
                        )

            # Theme → risk_factor edges
            for theme, factors in self.RISK_FACTORS.items():
                if theme_weights.get(theme, 0) <= 0 and theme not in {"CRYPTO", "FCN_UNDERLYING"}:
                    continue
                if theme == "FCN_UNDERLYING" and not fcn_linked_symbols:
                    continue
                if theme == "CRYPTO" and theme_weights.get("CRYPTO", 0) <= 0:
                    continue
                for factor in factors:
                    add_node(factor, "risk_factor")
                    edges.append(
                        ExposureGraphEdge(
                            source=theme,
                            target=factor,
                            edge_type="theme_in_risk",
                            weight=round(theme_weights.get(theme, 0), 2),
                        )
                    )

            repeated = sorted(
                [sym for sym, count in underlying_counts.items() if count >= 2]
            )
            dominant_themes = [
                theme for theme, _ in theme_weights.most_common(3) if theme_weights[theme] > 0
            ]

            return ExposureGraphSummary(
                nodes=list(nodes.values()),
                edges=edges,
                repeated_underlyings=repeated,
                dominant_themes=dominant_themes,
                high_beta_symbols=sorted(high_beta_symbols),
                fcn_linked_symbols=sorted(fcn_linked_symbols),
            )
        except Exception:
            return ExposureGraphSummary()
