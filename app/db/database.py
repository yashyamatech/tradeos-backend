import logging
import re
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


def _build_url(raw: str) -> tuple[str, dict]:
    """Return (asyncpg URL, connect_args).
    Strips ?sslmode= from the URL and converts it to asyncpg connect_args.
    """
    url = raw
    # Normalise postgres:// -> postgresql://
    if url.startswith("postgres://"):
        url = "postgresql" + url[len("postgres"):]
    # Inject asyncpg driver
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Extract sslmode from query string (asyncpg uses connect_args instead)
    ssl = False
    if "sslmode=" in url:
        if "sslmode=require" in url or "sslmode=verify" in url:
            ssl = True
        url = re.sub(r"[?&]sslmode=[^&]*", "", url).rstrip("?&")

    connect_args: dict = {}
    if ssl:
        connect_args["ssl"] = "require"

    return url, connect_args


def init_engine() -> None:
    global _engine, _AsyncSessionLocal
    if not settings.database_url:
        logger.warning("DATABASE_URL not set — database features disabled")
        return
    try:
        url, connect_args = _build_url(settings.database_url)
        logger.info("Connecting to DB (ssl=%s)", connect_args.get("ssl", False))
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
        raise RuntimeError("Database not configured — set DATABASE_URL env var")
    async with _AsyncSessionLocal() as session:
        yield session


init_engine()
