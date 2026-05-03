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


app.include_router(api_router, prefix="/api/v1")
