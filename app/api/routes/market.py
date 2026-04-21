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


@router.get("/holdings/raw")
async def get_holdings_raw():
    """Debug: returns the first holding with all fields visible."""
    try:
        session = await kotak_auth.get_session()
        result = await asyncio.to_thread(session.client.holdings)
        raw = result if isinstance(result, list) else result.get("data", result)
        return {
            "total": len(raw) if isinstance(raw, list) else None,
            "first_item": raw[0] if isinstance(raw, list) and raw else raw,
            "all_keys": list(raw[0].keys()) if isinstance(raw, list) and raw and isinstance(raw[0], dict) else None,
            "raw_response": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    return {"symbol": symbol, "ltp": None}
