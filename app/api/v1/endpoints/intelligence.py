from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Portfolio, User
from app.services.intelligence.schemas import PortfolioIntelligenceResponse
from app.services.intelligence.service import PortfolioIntelligenceService
from app.services.news.priority_engine import PortfolioPriorityEngine
from app.services.news.schemas import PortfolioNewsResponse, PortfolioPriorityResponse
from app.services.news.service import NewsService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/news/portfolio", response_model=PortfolioNewsResponse)
def get_portfolio_news(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")

    return NewsService(db).get_portfolio_news(portfolio)


@router.get("/priority", response_model=PortfolioPriorityResponse)
def get_portfolio_priority(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        return PortfolioPriorityEngine().build_priority_response([])

    try:
        return NewsService(db).get_portfolio_priority(portfolio)
    except Exception:
        return PortfolioPriorityEngine().build_priority_response([])


@router.get("/portfolio", response_model=PortfolioIntelligenceResponse)
def get_portfolio_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Current user has no portfolio")

    return PortfolioIntelligenceService(db).get_portfolio_intelligence(portfolio)
