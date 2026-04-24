import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.models.trade import Trade, TradeDirection, TradeStatus

router = APIRouter()


class TradeIn(BaseModel):
    symbol:      str
    direction:   str            # BUY | SELL
    quantity:    int = 1
    entry_price: float
    stop_loss:   float = 0
    target:      float = 0
    notes:       Optional[str] = None


class TradeOut(BaseModel):
    id:          str
    symbol:      str
    direction:   str
    quantity:    int
    entry_price: float
    stop_loss:   float
    target:      float
    exit_price:  Optional[float] = None
    pnl:         Optional[float] = None
    status:      str
    notes:       Optional[str] = None
    created_at:  str
    closed_at:   Optional[str] = None

    model_config = {"from_attributes": True}


def _out(t: Trade) -> TradeOut:
    return TradeOut(
        id=t.id,
        symbol=t.symbol,
        direction=t.direction.value if hasattr(t.direction, "value") else str(t.direction),
        quantity=t.quantity,
        entry_price=t.entry_price,
        stop_loss=t.stop_loss or 0,
        target=t.target or 0,
        exit_price=t.exit_price,
        pnl=t.pnl,
        status=t.status.value if hasattr(t.status, "value") else str(t.status),
        notes=t.notes,
        created_at=t.created_at.isoformat() if t.created_at else "",
        closed_at=t.closed_at.isoformat() if t.closed_at else None,
    )


@router.post("/", response_model=TradeOut, status_code=201)
async def create_trade(body: TradeIn, db: AsyncSession = Depends(get_db)):
    try:
        direction = TradeDirection(body.direction.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")
    trade = Trade(
        id=str(uuid.uuid4()),
        symbol=body.symbol.upper(),
        direction=direction,
        quantity=body.quantity,
        entry_price=body.entry_price,
        stop_loss=body.stop_loss,
        target=body.target,
        notes=body.notes,
        status=TradeStatus.OPEN,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return _out(trade)


@router.get("/", response_model=list[TradeOut])
async def list_trades(
    status: Optional[str] = Query(None, description="open | closed"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Trade).order_by(Trade.created_at.desc())
    if status:
        try:
            stmt = stmt.where(Trade.status == TradeStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")
    result = await db.execute(stmt)
    return [_out(t) for t in result.scalars().all()]


@router.post("/{trade_id}/close", response_model=TradeOut)
async def close_trade(
    trade_id: str,
    exit_price: float = Query(...),
    db: AsyncSession = Depends(get_db),
):
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status == TradeStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Trade already closed")
    trade.exit_price = exit_price
    trade.status = TradeStatus.CLOSED
    trade.closed_at = datetime.now(timezone.utc)
    # P&L: positive for BUY if price rose, for SELL if price fell
    if trade.direction == TradeDirection.BUY:
        trade.pnl = round((exit_price - trade.entry_price) * trade.quantity, 2)
    else:
        trade.pnl = round((trade.entry_price - exit_price) * trade.quantity, 2)
    await db.commit()
    await db.refresh(trade)
    return _out(trade)


@router.delete("/{trade_id}")
async def delete_trade(trade_id: str, db: AsyncSession = Depends(get_db)):
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.delete(trade)
    await db.commit()
    return {"ok": True}
