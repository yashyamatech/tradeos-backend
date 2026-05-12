import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from app.db.database import get_db
from app.models.lot import StockLot

router = APIRouter()


class LotIn(BaseModel):
    symbol:   str
    lot_size: int
    notes:    str | None = None

    @field_validator("symbol")
    @classmethod
    def upper_strip(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("lot_size")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("lot_size must be positive")
        return v


def _out(lot: StockLot) -> dict:
    return {
        "id":         lot.id,
        "symbol":     lot.symbol,
        "lot_size":   lot.lot_size,
        "notes":      lot.notes,
        "created_at": lot.created_at.isoformat() if lot.created_at else "",
        "updated_at": lot.updated_at.isoformat() if lot.updated_at else "",
    }


@router.get("/")
async def list_lots(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockLot).order_by(StockLot.symbol))
    return [_out(l) for l in result.scalars().all()]


@router.post("/", status_code=201)
async def create_lot(body: LotIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(StockLot).where(StockLot.symbol == body.symbol))
    if existing.scalar_one_or_none():
        raise HTTPException(400, detail=f"{body.symbol} already exists — use edit to update it")
    now = datetime.utcnow()
    lot = StockLot(
        id=str(uuid.uuid4()),
        symbol=body.symbol,
        lot_size=body.lot_size,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(lot)
    await db.commit()
    await db.refresh(lot)
    return _out(lot)


@router.put("/{lot_id}")
async def update_lot(lot_id: str, body: LotIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockLot).where(StockLot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(404, detail="Lot not found")
    # Check symbol uniqueness if changed
    if lot.symbol != body.symbol:
        dup = await db.execute(select(StockLot).where(StockLot.symbol == body.symbol))
        if dup.scalar_one_or_none():
            raise HTTPException(400, detail=f"{body.symbol} already exists")
    lot.symbol     = body.symbol
    lot.lot_size   = body.lot_size
    lot.notes      = body.notes
    lot.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(lot)
    return _out(lot)


@router.delete("/{lot_id}", status_code=204)
async def delete_lot(lot_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StockLot).where(StockLot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(404, detail="Lot not found")
    await db.delete(lot)
    await db.commit()
