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

# CORS：允許 Vercel 前端與本機開發環境呼叫 Render 後端
# - settings.cors_origins 保留原本 .env / config 設定
# - allow_origin_regex 允許 Vercel preview / production 子網域
def _normalize_cors_origins(value):
    if not value:
        return []
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return [origin for origin in value if origin]


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        dict.fromkeys(
            _normalize_cors_origins(settings.cors_origins)
            + [
                "https://ixai-website-clean.vercel.app",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        )
    ),
    allow_origin_regex=r"https://.*\.vercel\.app",
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


app.include_router(api_router, prefix="/api/v1")
