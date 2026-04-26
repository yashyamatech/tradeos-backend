from sqlalchemy import Column, String, Float, Integer, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


class TradeDirection(str, enum.Enum):
    BUY  = "BUY"
    SELL = "SELL"


class TradeStatus(str, enum.Enum):
    OPEN   = "open"
    CLOSED = "closed"


def _utcnow() -> datetime:
    """Timezone-naive UTC now — asyncpg requires naive datetimes for TIMESTAMP columns."""
    return datetime.utcnow()


class Trade(Base):
    __tablename__ = "trades"

    id          = Column(String,  primary_key=True)
    symbol      = Column(String,  nullable=False)
    direction   = Column(Enum(TradeDirection), nullable=False)
    quantity    = Column(Integer, nullable=False, default=1)
    entry_price = Column(Float,   nullable=False)
    stop_loss   = Column(Float,   nullable=False, default=0)
    target      = Column(Float,   nullable=False, default=0)
    exit_price  = Column(Float,   nullable=True)
    pnl         = Column(Float,   nullable=True)
    status      = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    notes       = Column(String,  nullable=True)
    created_at  = Column(DateTime, default=_utcnow)
    closed_at   = Column(DateTime, nullable=True)
