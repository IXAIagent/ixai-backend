from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import CashPosition, CryptoPosition, FCNPosition, Portfolio, StockPosition
from app.services.fcn_monitor_service import FCNMonitorService
from app.services.intelligence.brief_engine import IntelligenceBriefEngine
from app.services.intelligence.correlation_engine import IntelligenceCorrelationEngine
from app.services.intelligence.copilot_service import IXAICopilotService
from app.services.intelligence.dna_engine import PortfolioDNAEngine
from app.services.intelligence.enrichment_engine import IntelligenceEnrichmentEngine
from app.services.intelligence.graph_engine import IntelligenceGraphEngine
from app.services.intelligence.long_memory import LongTermMemoryEngine
from app.services.intelligence.memory_service import IntelligenceMemoryService
from app.services.intelligence.narrative_engine import IntelligenceNarrativeEngine
from app.services.intelligence.persistent_memory import IntelligenceMemoryStore
from app.services.intelligence.predictive_engine import PredictiveDriftEngine
from app.services.intelligence.reasoning_engine import IntelligenceReasoningEngine
from app.services.intelligence.scenario_engine import ScenarioEngine
from app.services.intelligence.schemas import PortfolioIntelligenceResponse, ReasoningSystemResponse
from app.services.intelligence.scoring_engine import IntelligenceScoringEngine
from app.services.intelligence.theme_engine import ThemeEvolutionEngine
from app.services.intelligence.timeline_engine import IntelligenceTimelineEngine
from app.services.intelligence.workspace_engine import WorkspaceDecisionEngine
from app.services.news.priority_engine import PortfolioPriorityEngine
from app.services.news.service import NewsService


class PortfolioIntelligenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.news_service = NewsService(db)
        self.priority_engine = PortfolioPriorityEngine()
        self.scoring_engine = IntelligenceScoringEngine()
        self.enrichment_engine = IntelligenceEnrichmentEngine()
        self.correlation_engine = IntelligenceCorrelationEngine()
        self.workspace_engine = WorkspaceDecisionEngine()
        self.narrative_engine = IntelligenceNarrativeEngine()
        self.brief_engine = IntelligenceBriefEngine()
        self.memory_service = IntelligenceMemoryService()
        self.persistent_memory = IntelligenceMemoryStore()
        self.long_memory_engine = LongTermMemoryEngine(self.persistent_memory)
        self.scenario_engine = ScenarioEngine()
        self.graph_engine = IntelligenceGraphEngine()
        self.theme_engine = ThemeEvolutionEngine()
        self.reasoning_engine = IntelligenceReasoningEngine()
        self.predictive_engine = PredictiveDriftEngine()
        self.timeline_engine = IntelligenceTimelineEngine()
        self.dna_engine = PortfolioDNAEngine()
        self.copilot_service = IXAICopilotService()
        self.fcn_monitor = FCNMonitorService()

    def get_portfolio_intelligence(self, portfolio: Portfolio) -> PortfolioIntelligenceResponse:
        try:
            portfolio_payload = self._portfolio_payload(portfolio)
            news_response = self.news_service.get_portfolio_news(portfolio)
            articles = list(news_response.articles or [])
            priority_response = self.priority_engine.build_priority_response(articles)
            fcn_analysis = self._fcn_analysis(portfolio)
            alerts = list(priority_response.top_alerts or [])
            _ = self.enrichment_engine.enrich_articles(articles)

            scores = self.scoring_engine.score(portfolio_payload, articles, fcn_analysis, alerts)
            correlations = self.correlation_engine.correlate(portfolio_payload, articles, fcn_analysis)
            workspace = self.workspace_engine.decide(
                scores,
                critical_count=int(priority_response.critical_count or 0),
                high_count=int(priority_response.high_count or 0),
            )
            what_changed = self.memory_service.compare_and_store(str(portfolio.id), workspace, scores)
            historical_drift = self.persistent_memory.compare_historical_drift(str(portfolio.id), scores)
            if historical_drift:
                what_changed = f"{what_changed} {historical_drift}".strip()
            narrative = self.narrative_engine.narrate(
                scores,
                workspace,
                articles,
                correlations,
                what_changed_today=what_changed,
            )
            brief = self.brief_engine.build(scores, workspace, articles)
            self.persistent_memory.append_snapshot(
                str(portfolio.id),
                scores,
                workspace,
                narrative,
                alerts,
            )

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

    def get_scenarios(self, portfolio: Portfolio):
        context = self._analysis_context(portfolio)
        return self.scenario_engine.build_scenarios(
            context["portfolio_payload"],
            context["scores"],
            context["correlations"],
            context["fcn_analysis"],
        )

    def get_graph(self, portfolio: Portfolio):
        context = self._analysis_context(portfolio)
        return self.graph_engine.build_graph(
            context["portfolio_payload"],
            context["articles"],
            context["correlations"],
            context["fcn_analysis"],
        )

    def answer_copilot_question(self, portfolio: Portfolio, question: str) -> str:
        intelligence = self.get_portfolio_intelligence(portfolio)
        reasoning = self.get_reasoning_system(portfolio)
        return self.copilot_service.answer_question(question, {"intelligence": intelligence, "reasoning": reasoning})

    def get_reasoning_system(self, portfolio: Portfolio) -> ReasoningSystemResponse:
        try:
            context = self._analysis_context(portfolio)
            portfolio_id = str(portfolio.id)
            scores = context["scores"]
            articles = context["articles"]
            correlations = context["correlations"]
            fcn_analysis = context["fcn_analysis"]
            alerts = context["alerts"]
            priority_response = context["priority_response"]
            workspace = self.workspace_engine.decide(
                scores,
                critical_count=int(priority_response.critical_count or 0),
                high_count=int(priority_response.high_count or 0),
            )
            enrichment = self.enrichment_engine.enrich_articles(articles)
            long_memory = self.long_memory_engine.summarize(portfolio_id)
            themes = self.theme_engine.evolve(enrichment, articles, correlations, long_memory)
            scenarios = self.scenario_engine.build_scenarios(
                context["portfolio_payload"],
                scores,
                correlations,
                fcn_analysis,
            )
            what_changed_today = self.memory_service.compare_and_store(portfolio_id, workspace, scores)
            reasoning = self.reasoning_engine.reason(
                scores,
                scenarios,
                correlations,
                themes,
                workspace,
                long_memory,
                alerts,
                fcn_analysis,
                context["portfolio_payload"],
            )
            predictive = self.predictive_engine.predict(scores, workspace, long_memory, themes)
            timeline = self.timeline_engine.summarize(
                workspace,
                long_memory,
                themes,
                alerts,
                what_changed_today,
            )
            dna = self.dna_engine.analyze(context["portfolio_payload"], scores)
            return ReasoningSystemResponse(
                long_memory=long_memory,
                themes=themes,
                reasoning=reasoning,
                predictive=predictive,
                timeline=timeline,
                dna=dna,
                generated_at=datetime.now(timezone.utc),
                is_stale=False,
            )
        except Exception:
            return ReasoningSystemResponse(generated_at=datetime.now(timezone.utc), is_stale=True)

    def _analysis_context(self, portfolio: Portfolio) -> dict[str, Any]:
        portfolio_payload = self._portfolio_payload(portfolio)
        news_response = self.news_service.get_portfolio_news(portfolio)
        articles = list(news_response.articles or [])
        priority_response = self.priority_engine.build_priority_response(articles)
        fcn_analysis = self._fcn_analysis(portfolio)
        alerts = list(priority_response.top_alerts or [])
        self.enrichment_engine.enrich_articles(articles)
        scores = self.scoring_engine.score(portfolio_payload, articles, fcn_analysis, alerts)
        correlations = self.correlation_engine.correlate(portfolio_payload, articles, fcn_analysis)
        return {
            "portfolio_payload": portfolio_payload,
            "articles": articles,
            "priority_response": priority_response,
            "fcn_analysis": fcn_analysis,
            "alerts": alerts,
            "scores": scores,
            "correlations": correlations,
        }

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
