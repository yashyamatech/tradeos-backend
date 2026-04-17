from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()


class TradeEntry(BaseModel):
    symbol: str
    direction: str          # "BUY" or "SELL"
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    mode: str = "paper"     # "paper" or "live"


class TradeResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    mode: str
    status: str
    created_at: str


@router.post("/enter", response_model=TradeResponse)
async def enter_trade(trade: TradeEntry):
    """Enter a paper or live trade. Validates risk rules before execution."""
    risk = abs(trade.entry_price - trade.stop_loss) * trade.quantity
    if risk > 1500:
        raise HTTPException(status_code=400, detail=f"Risk ₹{risk:.0f} exceeds max ₹1,500")

    # TODO: persist to DB and route to live executor when mode=="live"
    return TradeResponse(
        id="placeholder",
        symbol=trade.symbol,
        direction=trade.direction,
        quantity=trade.quantity,
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        target=trade.target,
        mode=trade.mode,
        status="open",
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/open")
async def list_open_trades():
    """Return all open trades."""
    return {"trades": []}


@router.post("/{trade_id}/close")
async def close_trade(trade_id: str, exit_price: float):
    """Close a trade by ID."""
    return {"id": trade_id, "exit_price": exit_price, "status": "closed"}
