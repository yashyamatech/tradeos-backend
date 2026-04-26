import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.api.routes import auth, market, trades, nse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tradeos")


async def _ensure_db_schema(engine) -> None:
    """Drop and recreate the trades table if the schema is outdated."""
    from app.models.trade import Base

    async with engine.begin() as conn:
        # information_schema.columns never throws — safe to query unconditionally
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'trades' AND column_name = 'direction'"
        ))
        has_direction = (result.scalar() or 0) > 0

        if not has_direction:
            logger.warning("Trades table missing 'direction' column — rebuilding")
            # Drop the table and its dependent enum types so create_all starts clean
            await conn.execute(text("DROP TABLE IF EXISTS trades CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS tradedirection CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS tradestatus CASCADE"))
            logger.info("Stale trades table and enums dropped")

        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        logger.info("DATABASE_URL detected, initialising tables...")
        try:
            from app.db.database import get_engine
            engine = get_engine()
            if engine:
                await _ensure_db_schema(engine)
            else:
                logger.error("Engine is None — check DATABASE_URL and Railway logs")
        except Exception as exc:
            logger.error("Failed to initialise DB tables: %s", exc, exc_info=True)
    else:
        logger.warning("DATABASE_URL not set — database features disabled")

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
    return {"status": "ok", "db_configured": bool(settings.database_url)}
