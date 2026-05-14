from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import assets
from app.api.v1.endpoints import dashboard
from app.api.v1.endpoints import imports
from app.api.v1.endpoints import intelligence
from app.api.v1.endpoints import market
from app.api.v1.endpoints import portfolio_input

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(dashboard.router)
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(intelligence.router)
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(portfolio_input.router, prefix="/portfolio", tags=["portfolio"])
