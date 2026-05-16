from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    resolve_portfolio_for_user,
)
from app.core.config import is_development_env
from app.core.database import get_db
from app.core.i18n import resolve_locale_header
from app.models.models import Portfolio, User
from app.scheduler.intelligence_runner import run_intelligence_scheduler_once
from app.services.intelligence.engine_service import IntelligenceEngineService
from app.services.intelligence.schemas import (
    CopilotExplainRequest,
    CopilotExplainResponse,
    IntelligenceGraphResponse,
    MarketEngineSummaryResponse,
    PortfolioEngineSummaryResponse,
    PortfolioIntelligenceResponse,
    PortfolioSummaryV2AResponse,
    ReasoningSystemResponse,
    ScenarioResponse,
    TimelineIntelligenceResponse,
)
from app.services.intelligence.service import PortfolioIntelligenceService
from app.services.market_data.base import utc_now_iso
from app.services.news.priority_engine import PortfolioPriorityEngine
from app.services.news.schemas import PortfolioNewsResponse, PortfolioPriorityResponse
from app.services.news.service import NewsService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/news/portfolio", response_model=PortfolioNewsResponse)
def get_portfolio_news(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return NewsService(db).get_portfolio_news(portfolio)


@router.get("/priority", response_model=PortfolioPriorityResponse)
def get_portfolio_priority(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    try:
        return NewsService(db).get_portfolio_priority(portfolio)
    except Exception:
        return PortfolioPriorityEngine().build_priority_response([])


@router.get("/portfolio", response_model=PortfolioIntelligenceResponse)
def get_portfolio_intelligence(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return PortfolioIntelligenceService(db).get_portfolio_intelligence(portfolio)


@router.get("/portfolio-summary", response_model=PortfolioSummaryV2AResponse)
def get_portfolio_summary_v2a(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return PortfolioIntelligenceService(db).get_portfolio_summary_v2a(portfolio)


@router.get("/timeline", response_model=TimelineIntelligenceResponse)
def get_timeline_intelligence(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return PortfolioIntelligenceService(db).get_timeline_intelligence(portfolio)


@router.post("/admin/run-scheduler-once")
def run_intelligence_scheduler_admin_once(db: Session = Depends(get_db)):
    if not is_development_env():
        raise HTTPException(status_code=403, detail="Scheduler admin endpoint is development-only")

    return run_intelligence_scheduler_once(db=db, source="admin_endpoint")


@router.get("/reasoning", response_model=ReasoningSystemResponse)
def get_intelligence_reasoning(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return PortfolioIntelligenceService(db).get_reasoning_system(portfolio)


@router.get("/scenarios", response_model=ScenarioResponse)
def get_intelligence_scenarios(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    try:
        scenarios = PortfolioIntelligenceService(db).get_scenarios(portfolio)
        return ScenarioResponse(scenarios=scenarios, generated_at=utc_now_iso(), is_stale=False)
    except Exception:
        return ScenarioResponse(scenarios=[], generated_at=utc_now_iso(), is_stale=True)


@router.get("/graph", response_model=IntelligenceGraphResponse)
def get_intelligence_graph(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    return PortfolioIntelligenceService(db).get_graph(portfolio)


@router.get("/engine-summary", response_model=PortfolioEngineSummaryResponse)
def get_engine_summary(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    locale: str = Depends(resolve_locale_header),
    db: Session = Depends(get_db),
):
    """v4A: unified portfolio intelligence engine output."""
    try:
        return IntelligenceEngineService(db).portfolio_engine_summary(
            portfolio, locale=locale
        )
    except Exception:
        from datetime import datetime, timezone

        return PortfolioEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            generated_at=datetime.now(timezone.utc),
            is_stale=True,
            status="unavailable",
            stale_reason="orchestrator_error",
            degraded_reason="orchestrator_error",
            locale=locale,
        )


@router.get("/market-engine", response_model=MarketEngineSummaryResponse)
def get_market_engine_summary(
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    locale: str = Depends(resolve_locale_header),
    db: Session = Depends(get_db),
):
    """v4B: market intelligence engine output, scoped to the user's portfolio."""
    try:
        return IntelligenceEngineService(db).market_engine_summary(
            portfolio, locale=locale
        )
    except Exception:
        from datetime import datetime, timezone

        return MarketEngineSummaryResponse(
            portfolio_id=str(portfolio.id),
            generated_at=datetime.now(timezone.utc),
            is_stale=True,
            status="unavailable",
            stale_reason="orchestrator_error",
            degraded_reason="orchestrator_error",
            locale=locale,
        )


@router.post("/copilot/explain", response_model=CopilotExplainResponse)
def explain_with_copilot(
    payload: CopilotExplainRequest,
    portfolio: Portfolio = Depends(resolve_portfolio_for_user),
    db: Session = Depends(get_db),
):
    answer = PortfolioIntelligenceService(db).answer_copilot_question(
        portfolio,
        payload.question or "",
        query_type=payload.query_type,
    )
    return CopilotExplainResponse(
        answer=answer,
        supported_topics=[
            "workspace mode",
            "top risks",
            "FCN sensitivity",
            "AI momentum",
            "crypto volatility",
            "biggest_risk",
            "why_today_focus",
            "fcn_risk",
            "portfolio_drift",
            "market_impact",
            "data_freshness",
        ],
        generated_at=utc_now_iso(),
        is_stale=False,
    )
