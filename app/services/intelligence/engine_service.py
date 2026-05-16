"""v4 orchestrator: calls the engines under `engines/` and assembles the
portfolio-engine + market-engine summary responses.

Built on top of `PortfolioIntelligenceService._analysis_context`, so it
reuses the existing scoring / news / FCN plumbing. No new DB calls beyond
what the underlying service already performs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.models import Portfolio
from app.services.intelligence.engines.concentration_engine import ConcentrationEngine
from app.services.intelligence.engines.exposure_graph_engine import ExposureGraphEngine
from app.services.intelligence.engines.fcn_systemic_risk_engine import (
    FCNSystemicRiskEngine,
)
from app.services.intelligence.engines.intelligence_score_engine import (
    IntelligenceScoreEngine,
)
from app.services.intelligence.engines.macro_news_risk_engine import (
    MacroNewsRiskEngine,
)
from app.services.intelligence.engines.market_regime_engine import MarketRegimeEngine
from app.services.intelligence.engines.portfolio_drift_engine import (
    PortfolioDriftEngine,
)
from app.services.intelligence.engines.portfolio_market_impact_engine import (
    PortfolioMarketImpactEngine,
)
from app.services.intelligence.engines.risk_propagation_engine import (
    RiskPropagationEngine,
)
from app.services.intelligence.engines.volatility_state_engine import (
    VolatilityStateEngine,
)
from app.services.intelligence.schemas import (
    ConcentrationSummary,
    ExposureGraphSummary,
    FCNSystemicRiskSummary,
    MacroNewsRiskSummary,
    MarketEngineSummaryResponse,
    MarketRegimeSummary,
    PortfolioDriftSummary,
    PortfolioEngineSummaryResponse,
    PortfolioMarketImpactSummary,
    RiskPropagationSummary,
    UnifiedIntelligenceScore,
    VolatilityStateSummary,
)
from app.services.intelligence.service import PortfolioIntelligenceService

logger = logging.getLogger(__name__)


class IntelligenceEngineService:
    """Thin orchestrator. All inner engines are fail-soft; this layer only
    arranges them and ensures responses never raise."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.intelligence = PortfolioIntelligenceService(db)
        self.exposure_graph = ExposureGraphEngine()
        self.concentration = ConcentrationEngine()
        self.fcn_systemic = FCNSystemicRiskEngine()
        self.drift = PortfolioDriftEngine()
        self.risk_propagation = RiskPropagationEngine()
        self.score_aggregator = IntelligenceScoreEngine()
        self.regime = MarketRegimeEngine()
        self.volatility = VolatilityStateEngine()
        self.macro_news = MacroNewsRiskEngine()
        self.market_impact = PortfolioMarketImpactEngine()

    # ------------------------------------------------------------------
    # v4A
    # ------------------------------------------------------------------
    def portfolio_engine_summary(
        self, portfolio: Portfolio
    ) -> PortfolioEngineSummaryResponse:
        now = datetime.now(timezone.utc)
        try:
            context = self.intelligence._analysis_context(portfolio)  # noqa: SLF001
        except Exception:
            logger.exception("engine_service: analysis_context failed")
            return PortfolioEngineSummaryResponse(
                portfolio_id=str(portfolio.id),
                generated_at=now,
                is_stale=True,
            )

        try:
            exposure = self.exposure_graph.analyse(context)
        except Exception:
            logger.exception("engine_service: exposure failed")
            exposure = ExposureGraphSummary()

        try:
            concentration = self.concentration.analyse(context)
        except Exception:
            logger.exception("engine_service: concentration failed")
            concentration = ConcentrationSummary()

        try:
            fcn_risk = self.fcn_systemic.analyse(context)
        except Exception:
            logger.exception("engine_service: fcn_systemic failed")
            fcn_risk = FCNSystemicRiskSummary()

        # Market regime + volatility feed both the drift engine and the
        # unified score. Computed here so v4A summary remains self-contained.
        try:
            regime = self.regime.analyse(context)
        except Exception:
            logger.exception("engine_service: regime failed")
            regime = MarketRegimeSummary()

        try:
            volatility = self.volatility.analyse(context)
        except Exception:
            logger.exception("engine_service: volatility failed")
            volatility = VolatilityStateSummary()

        try:
            drift = self.drift.analyse(
                portfolio_id=str(portfolio.id),
                current_concentration=concentration,
                current_regime=regime.regime,
                current_volatility_state=volatility.overall_state,
                current_fcn_pressure=context.get("scores").fcn_risk_score
                if context.get("scores") is not None
                else 0,
            )
        except Exception:
            logger.exception("engine_service: drift failed")
            drift = PortfolioDriftSummary()

        try:
            propagation = self.risk_propagation.analyse(
                exposure=exposure,
                concentration=concentration,
                fcn_risk=fcn_risk,
                drift=drift,
            )
        except Exception:
            logger.exception("engine_service: risk_propagation failed")
            propagation = RiskPropagationSummary()

        try:
            volatility_score = self._volatility_to_score(volatility)
            unified = self.score_aggregator.aggregate(
                scores=context.get("scores"),
                exposure=exposure,
                concentration=concentration,
                fcn_risk=fcn_risk,
                drift=drift,
                volatility_score=volatility_score,
            )
        except Exception:
            logger.exception("engine_service: unified score failed")
            unified = UnifiedIntelligenceScore()

        return PortfolioEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            exposure_graph=exposure,
            concentration=concentration,
            drift=drift,
            fcn_systemic_risk=fcn_risk,
            risk_propagation=propagation,
            unified_score=unified,
            generated_at=now,
            is_stale=False,
        )

    # ------------------------------------------------------------------
    # v4B
    # ------------------------------------------------------------------
    def market_engine_summary(
        self, portfolio: Portfolio
    ) -> MarketEngineSummaryResponse:
        now = datetime.now(timezone.utc)
        try:
            context = self.intelligence._analysis_context(portfolio)  # noqa: SLF001
        except Exception:
            logger.exception("engine_service: market analysis_context failed")
            return MarketEngineSummaryResponse(
                portfolio_id=str(portfolio.id),
                generated_at=now,
                is_stale=True,
            )

        try:
            regime = self.regime.analyse(context)
        except Exception:
            logger.exception("engine_service: regime failed")
            regime = MarketRegimeSummary()

        try:
            volatility = self.volatility.analyse(context)
        except Exception:
            logger.exception("engine_service: volatility failed")
            volatility = VolatilityStateSummary()

        try:
            macro = self.macro_news.analyse(context)
        except Exception:
            logger.exception("engine_service: macro_news failed")
            macro = MacroNewsRiskSummary()

        try:
            concentration = self.concentration.analyse(context)
            fcn_risk = self.fcn_systemic.analyse(context)
            impact = self.market_impact.analyse(
                context=context,
                concentration=concentration,
                fcn_risk=fcn_risk,
                regime=regime,
                volatility=volatility,
                macro=macro,
            )
        except Exception:
            logger.exception("engine_service: market_impact failed")
            impact = PortfolioMarketImpactSummary()

        return MarketEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            regime=regime,
            volatility=volatility,
            macro_news=macro,
            portfolio_impact=impact,
            generated_at=now,
            is_stale=False,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _volatility_to_score(self, vol: VolatilityStateSummary) -> float:
        mapping = {"low": 10.0, "normal": 30.0, "elevated": 60.0, "high": 85.0, "data_limited": 0.0}
        states = [
            mapping.get(vol.equity_volatility_state, 0.0),
            mapping.get(vol.crypto_volatility_state, 0.0),
            mapping.get(vol.fcn_sensitivity_state, 0.0),
        ]
        return max(states)
