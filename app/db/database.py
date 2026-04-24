import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from app.core.config import settings

logger = logging.getLogger("tradeos.db")

_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker | None = None


def init_engine() -> None:
    global _engine, _AsyncSessionLocal
    if not settings.database_url:
        logger.warning("DATABASE_URL not set — database features disabled")
        return
    _engine = create_async_engine(
        settings.async_db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("Async database engine initialised")


def get_engine() -> AsyncEngine | None:
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not configured — set DATABASE_URL env var")
    async with _AsyncSessionLocal() as session:
        yield session


# Initialise on import so the engine is ready before lifespan runs
init_engine()
