from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ 直接全開 CORS（避免任何 Vercel 問題）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 基本測試
@app.get("/")
def root():
    return {"status": "IXAI backend running"}

# ✅ Dashboard API（前端目前在用這個）
@app.get("/api/v1/dashboard/dev-real-summary")
def get_dashboard():
    return {
        "mode": "demo",
        "summary": "IXAI backend is live. Demo data is returned.",
        "alerts": [
            {"level": "medium", "message": "Backend connected"},
            {"level": "low", "message": "Demo data active"}
        ],
        "allocation": {
            "name": "US Stocks",
            "value": 58
        },
        "stocks": [
            {"symbol": "AAPL", "price": 190},
            {"symbol": "TSLA", "price": 180},
            {"symbol": "NVDA", "price": 140}
        ],
        "cash": {"currency": "USD", "amount": 25000},
        "fcn": [],
        "crypto": [],
        "risk_sources": [
            {"source": "FCN KI distance", "level": "medium"},
            {"source": "Grid range proximity", "level": "medium"}
        ],
        "summary_cards": [
            {"title": "Backend", "value": "Live"},
            {"title": "Frontend", "value": "Connected"},
            {"title": "Data", "value": "Demo"}
        ]
    }