from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import auth, market, trades, nse


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.kotak_service import kotak_service
    await kotak_service.init()
    yield
    await kotak_service.close()


app = FastAPI(title="TradeOS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(nse.router, prefix="/api/nse", tags=["nse"])


@app.get("/health")
async def health():
    return {"status": "ok"}
