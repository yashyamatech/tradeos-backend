from sqlalchemy import Column, String, Float, Integer, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


class TradeDirection(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    mode = Column(Enum(TradeMode), default=TradeMode.PAPER)
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    pnl = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
