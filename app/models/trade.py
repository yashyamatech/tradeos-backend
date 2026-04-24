from sqlalchemy import Column, String, Float, Integer, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
import enum


class Base(DeclarativeBase):
    pass


class TradeMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class Trade(Base):
    """F&O paper (or live) trade row."""
    __tablename__ = "trades"

    id              = Column(String, primary_key=True)
    symbol          = Column(String, nullable=False)            # e.g. NIFTY, HDFCBANK
    underlying_type = Column(String, nullable=False, default="index")  # index | equity
    option_type     = Column(String, nullable=False)            # CE | PE
    strike          = Column(Float,  nullable=False)
    expiry          = Column(String, nullable=False)            # e.g. "25-Apr-2024"
    lot_size        = Column(Integer, nullable=False, default=1)
    lots            = Column(Integer, nullable=False, default=1)
    entry_price     = Column(Float, nullable=False)
    stop_loss       = Column(Float, nullable=False, default=0)
    target          = Column(Float, nullable=False, default=0)
    exit_price      = Column(Float, nullable=True)
    pnl             = Column(Float, nullable=True)
    mode            = Column(Enum(TradeMode), default=TradeMode.PAPER)
    status          = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    notes           = Column(String, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at       = Column(DateTime, nullable=True)
