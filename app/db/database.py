import logging
import re
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger("tradeos.db")

_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker | None = None


def _build_url(raw: str) -> tuple[str, dict]:
    url = raw
    if url.startswith("postgres://"):
        url = "postgresql" + url[len("postgres"):]
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Parse explicit sslmode and strip it (asyncpg uses connect_args)
    ssl: str | bool | None = None
    if "sslmode=" in url:
        if "sslmode=disable" in url:
            ssl = False
        elif "sslmode=require" in url or "sslmode=verify" in url:
            ssl = "require"
        url = re.sub(r"[?&]sslmode=[^&]*", "", url).rstrip("?&")

    # Default: require SSL for any non-local host (covers Railway, Supabase, etc.)
    if ssl is None:
        is_local = any(h in url for h in ["localhost", "127.0.0.1", "::1", "@db:", "@postgres:"])
        ssl = False if is_local else "require"

    connect_args: dict = {}
    if ssl:
        connect_args["ssl"] = ssl

    logger.info("DB URL built (ssl=%s, host masked)", ssl)
    return url, connect_args


def init_engine() -> None:
    global _engine, _AsyncSessionLocal
    if not settings.database_url:
        logger.warning("DATABASE_URL not set — database features disabled")
        return
    try:
        url, connect_args = _build_url(settings.database_url)
        _engine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
            connect_args=connect_args,
        )
        _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
        logger.info("Async database engine initialised")
    except Exception as exc:
        logger.error("Failed to create DB engine: %s", exc, exc_info=True)


def get_engine() -> AsyncEngine | None:
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _AsyncSessionLocal is None:
        detail = (
            "Database not configured — DATABASE_URL is missing or the engine failed to "
            "initialise (check Railway logs for the startup error)."
        )
        raise HTTPException(status_code=500, detail=detail)
    try:
        async with _AsyncSessionLocal() as session:
            yield session
    except Exception as exc:
        logger.error("DB session error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database session error: {exc}")


init_engine()
