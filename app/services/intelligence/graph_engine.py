from __future__ import annotations

from typing import Any

from app.services.intelligence.schemas import (
    IntelligenceCorrelation,
    IntelligenceGraphEdge,
    IntelligenceGraphNode,
    IntelligenceGraphResponse,
)
from app.services.news.schemas import NewsArticle
from app.services.market_data.base import utc_now_iso


class IntelligenceGraphEngine:
    def build_graph(
        self,
        portfolio_payload: dict[str, Any],
        articles: list[NewsArticle],
        correlations: list[IntelligenceCorrelation],
        fcn_analysis: list[dict[str, Any]],
    ) -> IntelligenceGraphResponse:
        try:
            nodes: dict[str, IntelligenceGraphNode] = {}
            edges: list[IntelligenceGraphEdge] = []

            def node(node_id: str, label: str, node_type: str, weight: float = 1) -> None:
                if node_id and node_id not in nodes:
                    nodes[node_id] = IntelligenceGraphNode(id=node_id, label=label, node_type=node_type, weight=weight)

            def edge(source: str, target: str, edge_type: str, explanation: str) -> None:
                if source and target and len(edges) < 100:
                    edges.append(IntelligenceGraphEdge(source=source, target=target, edge_type=edge_type, explanation=explanation))

            for position in portfolio_payload.get("stock_positions", []):
                symbol = str(position.get("symbol") or "").upper()
                node(symbol, symbol, "symbol", 2)
                if symbol in {"NVDA", "MSFT", "AAPL", "TSM", "2330.TW", "AVGO", "MRVL", "PLTR", "MDB", "AMD"}:
                    node("AI_INFRA", "AI_INFRA", "theme", 3)
                    edge(symbol, "AI_INFRA", "theme", "AI/chip exposure linkage")

            for position in portfolio_payload.get("crypto_positions", []):
                symbol = str(position.get("symbol") or "").upper()
                node(symbol, symbol, "symbol", 2)
                node("CRYPTO_VOL", "CRYPTO_VOL", "theme", 3)
                edge(symbol, "CRYPTO_VOL", "theme", "Crypto volatility linkage")

            for fcn in portfolio_payload.get("fcn_positions", []):
                code = str(fcn.get("fcn_code") or fcn.get("name") or fcn.get("id") or "FCN")
                fcn_node = f"FCN:{code}"
                node(fcn_node, code, "fcn", 2)
                node("KI_RISK", "KI_RISK", "risk", 3)
                edge(fcn_node, "KI_RISK", "risk", "Structured product KI/KO sensitivity")

            for item in fcn_analysis:
                symbol = str(item.get("worst_symbol") or item.get("worst_of") or "").upper()
                code = str(item.get("fcn_code") or "FCN")
                if symbol:
                    node(symbol, symbol, "symbol", 2)
                    node(f"FCN:{code}", code, "fcn", 2)
                    edge(symbol, f"FCN:{code}", "underlying", "Worst-of / underlying relationship")
                    edge(symbol, "KI_RISK", "risk", "Worst-of movement can affect KI distance")

            for article in articles[:20]:
                symbol = str(article.symbol or "").upper()
                if symbol:
                    node(symbol, symbol, "symbol", 1)
                    if article.is_fcn_related:
                        node("KI_RISK", "KI_RISK", "risk", 3)
                        edge(symbol, "KI_RISK", "news_risk", "FCN-related news risk")
                    if "macro" in str(article.title or "").lower() or "cpi" in str(article.title or "").lower():
                        node("MACRO_RISK", "MACRO_RISK", "macro", 2)
                        edge(symbol, "MACRO_RISK", "macro", "Macro-sensitive news linkage")

            for correlation in correlations:
                node(correlation.source_symbol, correlation.source_symbol, "symbol", 1)
                for related in correlation.related_symbols[:5]:
                    node(related, related, "related", 1)
                    edge(correlation.source_symbol, related, correlation.correlation_type, correlation.explanation)

            strongest_themes = [node_id for node_id, item in nodes.items() if item.node_type == "theme"][:5]
            strongest_connections = [f"{edge.source} → {edge.target}" for edge in edges[:8]]
            top_correlated_risks = [node_id for node_id, item in nodes.items() if item.node_type in {"risk", "macro"}][:5]

            return IntelligenceGraphResponse(
                nodes=list(nodes.values())[:50],
                edges=edges[:100],
                strongest_themes=strongest_themes,
                strongest_connections=strongest_connections,
                top_correlated_risks=top_correlated_risks,
                generated_at=utc_now_iso(),
                is_stale=False,
            )
        except Exception:
            return IntelligenceGraphResponse(generated_at=utc_now_iso(), is_stale=True)
