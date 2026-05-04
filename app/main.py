from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from app.api.v1.api import api_router
except ModuleNotFoundError:
    from app.api.v1.router import api_router
from app.core.config import settings


app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "IXAI backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
