import httpx
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import quote
from typing import Literal

router = APIRouter()

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

HEATMAP_TYPES = {
    "sectoral":    "Sectoral Indices",
    "broad":       "Broad Market Indices",
    "thematic":    "Thematic Indices",
    "strategy":    "Strategy Indices",
}


async def _nse_client() -> httpx.AsyncClient:
    """Open an httpx client and establish a valid NSE session cookie."""
    client = httpx.AsyncClient(timeout=20, follow_redirects=True)
    await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
    return client


@router.get("/heatmap")
async def sector_heatmap(
    type: str = Query(default="sectoral", description="sectoral | broad | thematic | strategy")
):
    """
    Uses NSE's dedicated heatmap API.
    Source: https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices
    """
    index_type = HEATMAP_TYPES.get(type.lower(), "Sectoral Indices")
    url = f"https://www.nseindia.com/api/heatmap-index?type={quote(index_type)}"

    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            data = r.json()

        # Response is a list of index objects
        raw = data if isinstance(data, list) else data.get("data", [])

        sectors = [
            {
                "name":       idx.get("indexSymbol") or idx.get("index") or idx.get("name"),
                "last":       idx.get("last") or idx.get("indexValue") or idx.get("lastPrice"),
                "change":     idx.get("variation") or idx.get("change"),
                "pctChange":  idx.get("percentChange") or idx.get("pChange") or idx.get("pct_change"),
                "open":       idx.get("open"),
                "high":       idx.get("high"),
                "low":        idx.get("low"),
                "yearHigh":   idx.get("yearHigh") or idx.get("52WH"),
                "yearLow":    idx.get("yearLow") or idx.get("52WL"),
                "advances":   idx.get("advances", 0),
                "declines":   idx.get("declines", 0),
                "unchanged":  idx.get("unchanged", 0),
            }
            for idx in raw
            if idx.get("indexSymbol") or idx.get("index") or idx.get("name")
        ]

        return {
            "sectors": sectors,
            "type": index_type,
            "count": len(sectors),
            "source": url,
        }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap/raw")
async def heatmap_raw(
    type: str = Query(default="sectoral")
):
    """Raw NSE heatmap response — use this to inspect exact field names."""
    index_type = HEATMAP_TYPES.get(type.lower(), "Sectoral Indices")
    url = f"https://www.nseindia.com/api/heatmap-index?type={quote(index_type)}"
    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}")
async def sector_stocks(index_name: str):
    """
    Constituent stocks for a given index with OHLCV + LTP.
    e.g. /api/nse/sector/NIFTY%20BANK
    """
    url = f"https://www.nseindia.com/api/equity-stockIndices?index={quote(index_name.upper())}"
    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            data = r.json()

        raw = data.get("data", [])
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
            for s in raw[1:]  # first row is the index itself
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
