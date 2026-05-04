from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine
import app.models.models  # 重要：載入所有 SQLAlchemy models，包含 User
from app.api.v1.router import api_router


app = FastAPI(
    title="IXAI Agent",
    description="一玄AI 投資監控系統",
    version="1.0.0",
)

templates = Jinja2Templates(directory="templates")

# MVP 階段：自動建立資料表
# 正式上線後建議改用 Alembic migration
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "IXAI Agent API is running",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "api": "/api/v1",
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )


@app.get("/input", response_class=HTMLResponse)
def input_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="input.html",
        context={}
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "IXAI Agent",
    }


# Demo fallback data: keep frontend alive even before real portfolio/database is seeded.
def _demo_dashboard_payload():
    return {
        "mode": "demo",
        "summary": "IXAI backend is live. Demo data is returned until real portfolio data is connected.",
        "alerts": [
            {"level": "medium", "message": "Backend deployed on Render and connected to Vercel."},
            {"level": "low", "message": "Demo data active. Next step: connect real FCN / stock / crypto positions."},
        ],
        "allocation": [
            {"name": "US Stocks", "value": 58},
            {"name": "FCN", "value": 30},
            {"name": "Crypto / Grid", "value": 12},
        ],
        "stocks": [
            {"symbol": "AAPL", "quantity": 100, "cost": 140.26, "price": 190.0, "pnl_pct": 35.5},
            {"symbol": "TSLA", "quantity": 50, "cost": 160.91, "price": 180.0, "pnl_pct": 11.9},
            {"symbol": "NVDA", "quantity": 10, "cost": 127.0, "price": 140.0, "pnl_pct": 10.2},
        ],
        "cash": {"currency": "USD", "amount": 25000},
        "fcn_positions": [
            {
                "name": "FCN219M",
                "underlyings": ["MDB", "AFRM", "MRVL", "TSLA"],
                "ki": 65,
                "ko": 100,
                "strike": 95,
                "risk_level": "medium",
            }
        ],
        "fcn_analysis": [
            {
                "name": "FCN219M",
                "worst_symbol": "TSLA",
                "distance_to_KI": 22.5,
                "distance_to_KO": 8.0,
                "risk_level": "medium",
            }
        ],
        "crypto": [
            {"symbol": "BTCUSDT", "strategy": "Long Grid", "range": "72000-82000", "risk_level": "medium"},
            {"symbol": "BNBUSDT", "strategy": "Long Grid", "range": "600-700", "risk_level": "low"},
        ],
        "risk_sources": [
            {"source": "FCN KI distance", "level": "medium"},
            {"source": "Grid range proximity", "level": "medium"},
        ],
        "summary_cards": [
            {"title": "Backend", "value": "Live"},
            {"title": "Frontend", "value": "Connected"},
            {"title": "Data", "value": "Demo"},
        ],
    }


@app.get("/api/v1/dashboard/dev-real-summary")
def demo_dashboard_summary():
    return _demo_dashboard_payload()


@app.get("/api/v1/dashboard/my-summary")
def my_dashboard_summary():
    return _demo_dashboard_payload()



app.include_router(api_router, prefix="/api/v1")
