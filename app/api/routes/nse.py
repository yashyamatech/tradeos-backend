import httpx
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import quote

router = APIRouter()

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

# Exactly two supported types
HEATMAP_URLS = {
    "sectoral": "https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices",
    "broad":    "https://www.nseindia.com/api/heatmap-index?type=Broad%20Market%20Indices",
}

STOCKS_BASE = "https://www.nseindia.com/api/heatmap-symbols"


async def _nse_client() -> httpx.AsyncClient:
    """Open httpx client and grab NSE session cookie."""
    client = httpx.AsyncClient(timeout=20, follow_redirects=True)
    await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
    return client


def _parse_index(idx: dict) -> dict:
    """Normalise an index object regardless of field name variant."""
    return {
        "name":      idx.get("indexSymbol") or idx.get("index") or idx.get("name") or "",
        "last":      idx.get("last") or idx.get("lastPrice") or idx.get("indexValue") or 0,
        "change":    idx.get("variation") or idx.get("change") or 0,
        "pctChange": idx.get("percentChange") or idx.get("pChange") or 0,
        "open":      idx.get("open") or 0,
        "high":      idx.get("high") or 0,
        "low":       idx.get("low") or 0,
        "advances":  idx.get("advances") or 0,
        "declines":  idx.get("declines") or 0,
        "unchanged": idx.get("unchanged") or 0,
    }


@router.get("/heatmap")
async def sector_heatmap(type: str = Query(default="sectoral", description="sectoral | broad")):
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            data = r.json()

        # NSE returns either a plain list or {"data": [...]}
        raw = data if isinstance(data, list) else data.get("data", [])
        sectors = [_parse_index(i) for i in raw if i.get("indexSymbol") or i.get("index") or i.get("name")]
        return {"sectors": sectors, "count": len(sectors), "source": url}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap/raw")
async def heatmap_raw(type: str = Query(default="sectoral")):
    """Inspect the raw NSE response to verify field names."""
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            return {"url": url, "data": r.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}")
async def sector_stocks(
    index_name: str,
    type: str = Query(default="sectoral", description="sectoral | broad"),
):
    """
    Sectoral:    /api/nse/sector/NIFTY%20AUTO?type=sectoral
    Broad:       /api/nse/sector/NIFTY%2050?type=broad

    Source URL pattern:
      https://www.nseindia.com/api/heatmap-symbols?type=Sectoral%20Indices&indices=NIFTY%20AUTO
      https://www.nseindia.com/api/heatmap-symbols?type=Broad%20Market%20Indices&indices=NIFTY%2050
    """
    type_label = "Sectoral Indices" if type.lower() == "sectoral" else "Broad Market Indices"
    url = f"{STOCKS_BASE}?type={quote(type_label)}&indices={quote(index_name.upper())}"

    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            data = r.json()

        raw = data if isinstance(data, list) else data.get("data", [])
        stocks = [
            {
                "symbol":      s.get("symbol"),
                "lastPrice":   s.get("lastPrice"),
                "high":        s.get("high"),
                "low":         s.get("low"),
                "change":      s.get("change"),
                "pctChange":   s.get("pChange"),
                "volume":      s.get("totalTradedVolume") or s.get("quantityTraded"),
                "vwap":        s.get("vwap"),
                "lastUpdated": s.get("lastUpdatedTime"),
                "series":      s.get("series"),
            }
            for s in raw
            if s.get("symbol")
        ]
        return {"index": index_name.upper(), "stocks": stocks, "count": len(stocks), "source": url}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}/raw")
async def sector_stocks_raw(index_name: str, type: str = Query(default="sectoral")):
    """Inspect raw constituent response to verify field names."""
    type_label = "Sectoral Indices" if type.lower() == "sectoral" else "Broad Market Indices"
    url = f"{STOCKS_BASE}?type={quote(type_label)}&indices={quote(index_name.upper())}"
    try:
        async with await _nse_client() as client:
            r = await client.get(url, headers=NSE_HEADERS)
            r.raise_for_status()
            return {"url": url, "data": r.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
