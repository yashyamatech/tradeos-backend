import httpx
from fastapi import APIRouter, HTTPException
from urllib.parse import quote

router = APIRouter()

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

SECTORS = {
    "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA",
    "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL", "NIFTY REALTY",
    "NIFTY MEDIA", "NIFTY ENERGY", "NIFTY FINANCIAL SERVICES",
    "NIFTY MIDCAP 100", "NIFTY SMALLCAP 100", "NIFTY INFRA",
    "NIFTY COMMODITIES", "NIFTY CONSUMPTION",
}


async def _nse_session() -> httpx.AsyncClient:
    """Return an httpx client with a live NSE session cookie."""
    client = httpx.AsyncClient(timeout=20, follow_redirects=True)
    await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
    return client


@router.get("/heatmap")
async def sector_heatmap():
    try:
        async with await _nse_session() as client:
            r = await client.get(
                "https://www.nseindia.com/api/allIndices",
                headers=NSE_HEADERS,
            )
            r.raise_for_status()
            data = r.json()

        sectors = [
            {
                "name": idx["index"],
                "last": idx.get("last"),
                "change": idx.get("variation"),
                "pctChange": idx.get("percentChange"),
                "open": idx.get("open"),
                "high": idx.get("high"),
                "low": idx.get("low"),
                "yearHigh": idx.get("yearHigh"),
                "yearLow": idx.get("yearLow"),
                "advances": idx.get("advances", 0),
                "declines": idx.get("declines", 0),
                "unchanged": idx.get("unchanged", 0),
            }
            for idx in data.get("data", [])
            if idx.get("index") in SECTORS
        ]
        return {"sectors": sectors, "timestamp": data.get("timestamp")}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}")
async def sector_stocks(index_name: str):
    """
    Returns all constituent stocks for the given index with
    open, high, low, previousClose, ltp, volume, change, pctChange.
    e.g. /api/nse/sector/NIFTY%20BANK
    """
    try:
        url = f"https://www.nseindia.com/api/equity-stockIndices?index={quote(index_name.upper())}"
        async with await _nse_session() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            data = r.json()

        raw = data.get("data", [])
        # First item is always the index summary itself — skip it
        stocks = [
            {
                "symbol":        s.get("symbol"),
                "open":          s.get("open"),
                "high":          s.get("dayHigh"),
                "low":           s.get("dayLow"),
                "previousClose": s.get("previousClose"),
                "ltp":           s.get("lastPrice"),
                "volume":        s.get("totalTradedVolume"),
                "change":        s.get("change"),
                "pctChange":     s.get("pChange"),
                "yearHigh":      s.get("52WH"),
                "yearLow":       s.get("52WL"),
            }
            for s in raw[1:]  # skip index row
        ]
        return {
            "index": index_name.upper(),
            "stocks": stocks,
            "timestamp": data.get("timestamp"),
            "count": len(stocks),
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices")
async def all_indices():
    try:
        async with await _nse_session() as client:
            r = await client.get("https://www.nseindia.com/api/allIndices", headers=NSE_HEADERS)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
