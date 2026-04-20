from fastapi import APIRouter

router = APIRouter()


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    # Placeholder — live quotes wired up after auth is confirmed
    return {"symbol": symbol, "ltp": None}
