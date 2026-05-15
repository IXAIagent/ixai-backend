from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import CashPosition, CryptoPosition, FCNPosition, Portfolio, StockPosition
from app.services.fcn_monitor_service import FCNMonitorService
from app.services.intelligence.brief_engine import IntelligenceBriefEngine
from app.services.intelligence.correlation_engine import IntelligenceCorrelationEngine
from app.services.intelligence.memory_service import IntelligenceMemoryService
from app.services.intelligence.narrative_engine import IntelligenceNarrativeEngine
from app.services.intelligence.schemas import PortfolioIntelligenceResponse
from app.services.intelligence.scoring_engine import IntelligenceScoringEngine
from app.services.intelligence.workspace_engine import WorkspaceDecisionEngine
from app.services.news.priority_engine import PortfolioPriorityEngine
from app.services.news.service import NewsService


class PortfolioIntelligenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.news_service = NewsService(db)
        self.priority_engine = PortfolioPriorityEngine()
        self.scoring_engine = IntelligenceScoringEngine()
        self.correlation_engine = IntelligenceCorrelationEngine()
        self.workspace_engine = WorkspaceDecisionEngine()
        self.narrative_engine = IntelligenceNarrativeEngine()
        self.brief_engine = IntelligenceBriefEngine()
        self.memory_service = IntelligenceMemoryService()
        self.fcn_monitor = FCNMonitorService()

    def get_portfolio_intelligence(self, portfolio: Portfolio) -> PortfolioIntelligenceResponse:
        try:
            portfolio_payload = self._portfolio_payload(portfolio)
            news_response = self.news_service.get_portfolio_news(portfolio)
            articles = list(news_response.articles or [])
            priority_response = self.priority_engine.build_priority_response(articles)
            fcn_analysis = self._fcn_analysis(portfolio)
            alerts = list(priority_response.top_alerts or [])

            scores = self.scoring_engine.score(portfolio_payload, articles, fcn_analysis, alerts)
            correlations = self.correlation_engine.correlate(portfolio_payload, articles, fcn_analysis)
            workspace = self.workspace_engine.decide(
                scores,
                critical_count=int(priority_response.critical_count or 0),
                high_count=int(priority_response.high_count or 0),
            )
            what_changed = self.memory_service.compare_and_store(str(portfolio.id), workspace, scores)
            narrative = self.narrative_engine.narrate(
                scores,
                workspace,
                articles,
                correlations,
                what_changed_today=what_changed,
            )
            brief = self.brief_engine.build(scores, workspace, articles)

            return PortfolioIntelligenceResponse(
                scores=scores,
                narrative=narrative,
                correlations=correlations,
                workspace=workspace,
                brief=brief,
                generated_at=datetime.now(timezone.utc),
                is_stale=False,
            )
        except Exception:
            return PortfolioIntelligenceResponse(
                generated_at=datetime.now(timezone.utc),
                is_stale=True,
            )

    def _portfolio_payload(self, portfolio: Portfolio) -> dict[str, Any]:
        stock_positions = [self._stock_payload(item) for item in self._stocks(portfolio)]
        crypto_positions = [self._crypto_payload(item) for item in self._cryptos(portfolio)]
        cash_positions = [self._cash_payload(item) for item in self._cash(portfolio)]
        fcn_positions = [self._fcn_payload(item) for item in self._fcns(portfolio)]

        stock_value = sum(self._float(item.get("current_value")) for item in stock_positions)
        crypto_value = sum(self._float(item.get("current_value")) for item in crypto_positions)
        cash_value = sum(self._float(item.get("amount")) for item in cash_positions)
        fcn_value = sum(self._float(item.get("notional_amount")) for item in fcn_positions)

        return {
            "portfolio_id": str(portfolio.id),
            "portfolio_name": str(portfolio.name),
            "total_value": stock_value + crypto_value + cash_value + fcn_value,
            "stock_value": stock_value,
            "crypto_value": crypto_value,
            "cash_value": cash_value,
            "fcn_value": fcn_value,
            "stock_positions": stock_positions,
            "crypto_positions": crypto_positions,
            "cash_summary": cash_positions,
            "fcn_positions": fcn_positions,
        }

    def _fcn_analysis(self, portfolio: Portfolio) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for fcn in self._fcns(portfolio):
            try:
                analysis = self.fcn_monitor.analyze(fcn)
                if analysis:
                    rows.append(analysis)
            except Exception:
                continue
        return rows

    def _stocks(self, portfolio: Portfolio) -> list[StockPosition]:
        return self.db.query(StockPosition).filter(StockPosition.portfolio_id == portfolio.id).all()

    def _cryptos(self, portfolio: Portfolio) -> list[CryptoPosition]:
        return self.db.query(CryptoPosition).filter(CryptoPosition.portfolio_id == portfolio.id).all()

    def _cash(self, portfolio: Portfolio) -> list[CashPosition]:
        return self.db.query(CashPosition).filter(CashPosition.portfolio_id == portfolio.id).all()

    def _fcns(self, portfolio: Portfolio) -> list[FCNPosition]:
        return self.db.query(FCNPosition).filter(FCNPosition.portfolio_id == portfolio.id).all()

    def _stock_payload(self, item: StockPosition) -> dict[str, Any]:
        quantity = self._float(getattr(item, "quantity", 0))
        current_price = self._float(getattr(item, "current_price", 0)) or self._float(getattr(item, "avg_price", 0))
        return {
            "id": getattr(item, "id", None),
            "symbol": getattr(item, "symbol", None),
            "quantity": quantity,
            "avg_price": self._float(getattr(item, "avg_price", 0)),
            "current_price": current_price,
            "current_value": self._float(getattr(item, "current_value", 0)) or quantity * current_price,
        }

    def _crypto_payload(self, item: CryptoPosition) -> dict[str, Any]:
        quantity = self._float(getattr(item, "quantity", 0))
        current_price = self._float(getattr(item, "current_price", 0)) or self._float(getattr(item, "avg_price", 0))
        return {
            "id": getattr(item, "id", None),
            "symbol": getattr(item, "symbol", None),
            "asset_type": getattr(item, "asset_type", None),
            "quantity": quantity,
            "avg_price": self._float(getattr(item, "avg_price", 0)),
            "current_price": current_price,
            "current_value": self._float(getattr(item, "current_value", 0)) or quantity * current_price,
            "leverage": self._float(getattr(item, "leverage", 0)),
        }

    def _cash_payload(self, item: CashPosition) -> dict[str, Any]:
        return {
            "id": getattr(item, "id", None),
            "currency": getattr(item, "currency", None),
            "amount": self._float(getattr(item, "amount", 0)),
        }

    def _fcn_payload(self, item: FCNPosition) -> dict[str, Any]:
        return {
            "id": getattr(item, "id", None),
            "name": getattr(item, "name", None),
            "fcn_code": getattr(item, "fcn_code", None),
            "notional_amount": self._float(
                getattr(item, "notional_amount", None)
                if getattr(item, "notional_amount", None) is not None
                else getattr(item, "notional", 0)
            ),
            "underlyings": getattr(item, "underlyings", None),
            "risk_level": getattr(item, "risk_level", None),
        }

    def _float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
