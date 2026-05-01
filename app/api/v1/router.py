from fastapi import APIRouter
from app.api.v1.endpoints import auth, dashboard, portfolio_input

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(portfolio_input.router)
