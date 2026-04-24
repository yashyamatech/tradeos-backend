import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.routes import auth, market, trades, nse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tradeos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables (no-op if DATABASE_URL not set)
    if settings.database_url:
        from app.db.database import get_engine
        from app.models.trade import Base
        engine = get_engine()
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ready")

    # Init Kotak Neo client
    from app.services.kotak_service import kotak_service
    await kotak_service.init()
    yield
    await kotak_service.close()


app = FastAPI(title="TradeOS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)
    expected = settings.backend_api_key
    if expected:
        provided = request.headers.get("X-API-Key", "")
        if provided != expected:
            ip = request.client.host if request.client else "unknown"
            logger.warning("Forbidden: bad API key from %s -> %s", ip, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden"},
            )
    return await call_next(request)


app.include_router(auth.router,   prefix="/api/auth",   tags=["auth"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(nse.router,    prefix="/api/nse",    tags=["nse"])


@app.get("/health")
async def health():
    return {"status": "ok"}
