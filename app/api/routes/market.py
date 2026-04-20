import asyncio
from fastapi import APIRouter, HTTPException

from app.core.auth.kotak_neo import kotak_auth

router = APIRouter()


@router.get("/holdings")
async def get_holdings():
    try:
        session = await kotak_auth.get_session()
        result = await asyncio.to_thread(session.client.holdings)
        return {"holdings": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    return {"symbol": symbol, "ltp": None}
