import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.auth.kotak_neo import kotak_auth

router = APIRouter()
logger = logging.getLogger("tradeos.market")


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
    try:
        session = await kotak_auth.get_session()
        result = await asyncio.to_thread(session.client.holdings)
        raw = result if isinstance(result, list) else result.get("data", result)
        return {
            "total": len(raw) if isinstance(raw, list) else None,
            "first_item": raw[0] if isinstance(raw, list) and raw else raw,
            "all_keys": list(raw[0].keys()) if isinstance(raw, list) and raw and isinstance(raw[0], dict) else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_instrument(
    symbol: str = Query(...),
    exchange: str = Query(default="nse_fo"),
):
    """Search Kotak scrip master for options/futures/equity by symbol."""
    try:
        session = await kotak_auth.get_session()
        result = await asyncio.to_thread(
            session.client.search_scrip,
            exchange_segment=exchange,
            symbol=symbol.upper()
        )
        data = result.get("data", result) if isinstance(result, dict) else result
        return {"instruments": data or [], "count": len(data) if data else 0}
    except Exception as e:
        logger.error("search_scrip error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class LtpRequest(BaseModel):
    tokens: list[dict]


@router.post("/ltp")
async def get_ltp(body: LtpRequest):
    """Fetch live LTP for [{exchangeSegment, exchangeInstrumentID}] tokens via Kotak."""
    if not body.tokens:
        return {"data": []}
    try:
        session = await kotak_auth.get_session()
        result = await asyncio.to_thread(
            session.client.quotes,
            instrument_tokens=body.tokens,
            quote_type="ltp",
            isIndex=False
        )
        logger.info("LTP raw: %s", str(result)[:300])
        return result
    except Exception as e:
        logger.error("LTP error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
