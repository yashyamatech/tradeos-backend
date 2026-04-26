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

# Bump this when the trades schema changes to force a table rebuild on next deploy.
_SCHEMA_VERSION = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        logger.info("DATABASE_URL detected, initialising tables...")
        try:
            from app.db.database import get_engine
            from app.models.trade import Base
            engine = get_engine()
            if engine:
                async with engine.begin() as conn:
                    # Check whether the current schema is up to date.
                    # If the schema_version table doesn't exist, or the version
                    # is older than _SCHEMA_VERSION, drop and recreate all tables.
                    try:
                        row = await conn.execute(
                            text("SELECT version FROM schema_version WHERE table_name = 'trades'")
                        )
                        db_version = row.scalar()
                    except Exception:
                        db_version = None

                    if db_version != _SCHEMA_VERSION:
                        logger.warning(
                            "Schema version mismatch (db=%s, expected=%s) — rebuilding trades table",
                            db_version, _SCHEMA_VERSION,
                        )
                        await conn.execute(text("DROP TABLE IF EXISTS trades"))
                        await conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                        await conn.run_sync(Base.metadata.create_all)
                        await conn.execute(text(
                            "CREATE TABLE IF NOT EXISTS schema_version "
                            "(table_name TEXT PRIMARY KEY, version INTEGER)"
                        ))
                        await conn.execute(text(
                            f"INSERT INTO schema_version (table_name, version) "
                            f"VALUES ('trades', {_SCHEMA_VERSION}) "
                            f"ON CONFLICT (table_name) DO UPDATE SET version = EXCLUDED.version"
                        ))
                        logger.info("Trades table rebuilt at schema version %s", _SCHEMA_VERSION)
                    else:
                        await conn.run_sync(Base.metadata.create_all)
                        logger.info("Database tables ready (schema v%s)", _SCHEMA_VERSION)
            else:
                logger.error("Engine is None — check DATABASE_URL format")
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
