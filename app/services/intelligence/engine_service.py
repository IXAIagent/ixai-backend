"""v4 orchestrator: calls the engines under `engines/` and assembles the
portfolio-engine + market-engine summary responses.

Built on top of `PortfolioIntelligenceService._analysis_context`, so it
reuses the existing scoring / news / FCN plumbing. No new DB calls beyond
what the underlying service already performs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.cache import analysis_context_cache, engine_summary_cache
from app.core.i18n import DEFAULT_LOCALE, narrative_locale
from app.core.telemetry import TimingContext, record_event
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

T = TypeVar("T")


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
        self,
        portfolio: Portfolio,
        locale: str = DEFAULT_LOCALE,
    ) -> PortfolioEngineSummaryResponse:
        now = datetime.now(timezone.utc)
        narrative_loc = narrative_locale(locale)
        cache_key = ("engine", "portfolio", str(portfolio.id), narrative_loc)
        cached = engine_summary_cache.get(cache_key)
        if isinstance(cached, PortfolioEngineSummaryResponse):
            record_event(
                "engine_cache_hit", surface="portfolio_engine", portfolio_id=str(portfolio.id)
            )
            return cached

        failed: list[str] = []
        context = self._load_analysis_context(portfolio, failed)
        if context is None:
            response = PortfolioEngineSummaryResponse(
                portfolio_id=str(portfolio.id),
                generated_at=now,
                is_stale=True,
                status="unavailable",
                stale_reason="analysis_context_unavailable",
                degraded_reason="analysis_context_unavailable",
                locale=narrative_loc,
                failed_engines=["analysis_context"],
            )
            self._record_summary_telemetry(
                "portfolio_engine", response, portfolio.id, failed=["analysis_context"]
            )
            return response

        exposure = self._run("exposure_graph", failed, ExposureGraphSummary,
                             lambda: self.exposure_graph.analyse(context))
        concentration = self._run("concentration", failed, ConcentrationSummary,
                                  lambda: self.concentration.analyse(context))
        fcn_risk = self._run("fcn_systemic", failed, FCNSystemicRiskSummary,
                             lambda: self.fcn_systemic.analyse(context))
        regime = self._run("regime", failed, MarketRegimeSummary,
                           lambda: self.regime.analyse(context))
        volatility = self._run("volatility", failed, VolatilityStateSummary,
                               lambda: self.volatility.analyse(context))
        drift = self._run(
            "drift",
            failed,
            PortfolioDriftSummary,
            lambda: self.drift.analyse(
                portfolio_id=str(portfolio.id),
                current_concentration=concentration,
                current_regime=regime.regime,
                current_volatility_state=volatility.overall_state,
                current_fcn_pressure=context.get("scores").fcn_risk_score
                if context.get("scores") is not None
                else 0,
            ),
        )
        propagation = self._run(
            "risk_propagation",
            failed,
            RiskPropagationSummary,
            lambda: self.risk_propagation.analyse(
                exposure=exposure,
                concentration=concentration,
                fcn_risk=fcn_risk,
                drift=drift,
            ),
        )
        unified = self._run(
            "unified_score",
            failed,
            UnifiedIntelligenceScore,
            lambda: self.score_aggregator.aggregate(
                scores=context.get("scores"),
                exposure=exposure,
                concentration=concentration,
                fcn_risk=fcn_risk,
                drift=drift,
                volatility_score=self._volatility_to_score(volatility),
            ),
        )

        status, stale, stale_reason, degraded_reason = self._classify_status(failed)
        response = PortfolioEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            exposure_graph=exposure,
            concentration=concentration,
            drift=drift,
            fcn_systemic_risk=fcn_risk,
            risk_propagation=propagation,
            unified_score=unified,
            generated_at=now,
            is_stale=stale,
            status=status,
            stale_reason=stale_reason,
            degraded_reason=degraded_reason,
            locale=narrative_loc,
            failed_engines=failed,
        )
        engine_summary_cache.set(cache_key, response)
        self._record_summary_telemetry(
            "portfolio_engine", response, portfolio.id, failed=failed
        )
        return response

    # ------------------------------------------------------------------
    # v4B
    # ------------------------------------------------------------------
    def market_engine_summary(
        self,
        portfolio: Portfolio,
        locale: str = DEFAULT_LOCALE,
    ) -> MarketEngineSummaryResponse:
        now = datetime.now(timezone.utc)
        narrative_loc = narrative_locale(locale)
        cache_key = ("engine", "market", str(portfolio.id), narrative_loc)
        cached = engine_summary_cache.get(cache_key)
        if isinstance(cached, MarketEngineSummaryResponse):
            record_event(
                "engine_cache_hit", surface="market_engine", portfolio_id=str(portfolio.id)
            )
            return cached

        failed: list[str] = []
        context = self._load_analysis_context(portfolio, failed)
        if context is None:
            response = MarketEngineSummaryResponse(
                portfolio_id=str(portfolio.id),
                generated_at=now,
                is_stale=True,
                status="unavailable",
                stale_reason="analysis_context_unavailable",
                degraded_reason="analysis_context_unavailable",
                locale=narrative_loc,
                failed_engines=["analysis_context"],
            )
            self._record_summary_telemetry(
                "market_engine", response, portfolio.id, failed=["analysis_context"]
            )
            return response

        regime = self._run("regime", failed, MarketRegimeSummary,
                           lambda: self.regime.analyse(context))
        volatility = self._run("volatility", failed, VolatilityStateSummary,
                               lambda: self.volatility.analyse(context))
        macro = self._run("macro_news", failed, MacroNewsRiskSummary,
                          lambda: self.macro_news.analyse(context))
        concentration = self._run("concentration", failed, ConcentrationSummary,
                                  lambda: self.concentration.analyse(context))
        fcn_risk = self._run("fcn_systemic", failed, FCNSystemicRiskSummary,
                             lambda: self.fcn_systemic.analyse(context))
        impact = self._run(
            "market_impact",
            failed,
            PortfolioMarketImpactSummary,
            lambda: self.market_impact.analyse(
                context=context,
                concentration=concentration,
                fcn_risk=fcn_risk,
                regime=regime,
                volatility=volatility,
                macro=macro,
            ),
        )

        status, stale, stale_reason, degraded_reason = self._classify_status(failed)
        response = MarketEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            regime=regime,
            volatility=volatility,
            macro_news=macro,
            portfolio_impact=impact,
            generated_at=now,
            is_stale=stale,
            status=status,
            stale_reason=stale_reason,
            degraded_reason=degraded_reason,
            locale=narrative_loc,
            failed_engines=failed,
        )
        engine_summary_cache.set(cache_key, response)
        self._record_summary_telemetry(
            "market_engine", response, portfolio.id, failed=failed
        )
        return response

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

    def _load_analysis_context(
        self, portfolio: Portfolio, failed: list[str]
    ) -> dict[str, Any] | None:
        """Cached + telemetered access to PortfolioIntelligenceService context."""
        cache_key = ("analysis_context", str(portfolio.id))
        cached = analysis_context_cache.get(cache_key)
        if cached is not None:
            record_event(
                "analysis_context_cache_hit", portfolio_id=str(portfolio.id)
            )
            return cached
        with TimingContext("analysis_context_build", portfolio_id=str(portfolio.id)):
            try:
                context = self.intelligence._analysis_context(portfolio)  # noqa: SLF001
                analysis_context_cache.set(cache_key, context)
                return context
            except Exception:
                logger.exception("engine_service: analysis_context failed")
                failed.append("analysis_context")
                return None

    def _run(
        self,
        name: str,
        failed: list[str],
        fallback_cls: Callable[[], T],
        loader: Callable[[], T],
    ) -> T:
        """Run a single engine with telemetry + fallback. Adds the engine
        name to ``failed`` on exception."""
        with TimingContext("engine_step", engine_name=name):
            try:
                return loader()
            except Exception:
                logger.exception("engine_service: %s failed", name)
                failed.append(name)
                return fallback_cls()

    def _classify_status(
        self, failed: list[str]
    ) -> tuple[str, bool, str, str]:
        """Map the failed-engines list to (status, is_stale, stale_reason, degraded_reason).

        Bands:
            healthy   - no failure
            partial   - 1 engine failed
            degraded  - 2+ engines failed, response still usable
            unavailable - context unavailable (handled outside)
        """
        if not failed:
            return "healthy", False, "", ""
        joined = ",".join(failed)
        if len(failed) == 1:
            return "partial", False, "", f"engine_failed:{joined}"
        return "degraded", True, "multiple_engines_failed", f"engines_failed:{joined}"

    def _record_summary_telemetry(
        self,
        surface: str,
        response: Any,
        portfolio_id: Any,
        *,
        failed: list[str],
    ) -> None:
        try:
            record_event(
                "engine_summary",
                surface=surface,
                portfolio_id=str(portfolio_id),
                status=getattr(response, "status", "unknown"),
                is_stale=bool(getattr(response, "is_stale", False)),
                failed_count=len(failed),
            )
        except Exception:
            pass
