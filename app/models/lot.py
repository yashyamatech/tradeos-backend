from sqlalchemy import Column, String, Integer, DateTime
from app.models.base import Base
from datetime import datetime


def _utcnow() -> datetime:
    return datetime.utcnow()


class StockLot(Base):
    __tablename__ = "stock_lots"

    id         = Column(String,  primary_key=True)
    symbol     = Column(String,  nullable=False, unique=True)
    lot_size   = Column(Integer, nullable=False)
    notes      = Column(String,  nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow)
