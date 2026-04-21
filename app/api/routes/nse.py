import logging
import httpx
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import quote

router = APIRouter()
logger = logging.getLogger("tradeos.nse")

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

HEATMAP_URLS = {
    "sectoral": "https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices",
    "broad":    "https://www.nseindia.com/api/heatmap-index?type=Broad%20Market%20Indices",
}

STOCKS_BASE = "https://www.nseindia.com/api/heatmap-symbols"


def _num(val) -> float:
    """Parse NSE numeric values that may arrive as strings with commas."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


async def _nse_get(url: str) -> dict:
    """Establish NSE session cookie then fetch url in a single client lifecycle."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
        r = await client.get(url, headers=NSE_HEADERS)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            logger.info("NSE %s -> list[%d], first keys: %s", url.split('?')[1], len(data),
                        list(data[0].keys())[:8] if data and isinstance(data[0], dict) else "empty")
        else:
            logger.info("NSE %s -> dict keys: %s", url.split('?')[1], list(data.keys())[:8] if isinstance(data, dict) else type(data))
        return data


def _parse_index(idx: dict) -> dict:
    return {
        "name":      (idx.get("indexSymbol") or idx.get("index") or idx.get("name") or ""),
        "last":      _num(idx.get("last") or idx.get("lastPrice") or idx.get("indexValue") or idx.get("currentValue")),
        "change":    _num(idx.get("variation") or idx.get("change") or idx.get("netChange")),
        "pctChange": _num(idx.get("percentChange") or idx.get("pChange") or idx.get("perChange")),
        "open":      _num(idx.get("open")),
        "high":      _num(idx.get("high")),
        "low":       _num(idx.get("low")),
        "advances":  int(idx.get("advances") or 0),
        "declines":  int(idx.get("declines") or 0),
        "unchanged": int(idx.get("unchanged") or 0),
    }


@router.get("/heatmap")
async def sector_heatmap(type: str = Query(default="sectoral", description="sectoral | broad")):
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        data = await _nse_get(url)
        raw = data if isinstance(data, list) else data.get("data", [])
        sectors = [_parse_index(i) for i in raw if i.get("indexSymbol") or i.get("index") or i.get("name")]
        logger.info("Heatmap %s: %d sectors parsed", type, len(sectors))
        return {"sectors": sectors, "count": len(sectors), "source": url}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap/raw")
async def heatmap_raw(type: str = Query(default="sectoral")):
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        return {"url": url, "data": await _nse_get(url)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}")
async def sector_stocks(
    index_name: str,
    type: str = Query(default="sectoral", description="sectoral | broad"),
):
    type_label = "Sectoral Indices" if type.lower() == "sectoral" else "Broad Market Indices"
    url = f"{STOCKS_BASE}?type={quote(type_label)}&indices={quote(index_name.upper())}"
    try:
        data = await _nse_get(url)
        raw = data if isinstance(data, list) else data.get("data", [])
        stocks = [
            {
                "symbol":      s.get("symbol"),
                "lastPrice":   _num(s.get("lastPrice")),
                "high":        _num(s.get("high")),
                "low":         _num(s.get("low")),
                "change":      _num(s.get("change")),
                "pctChange":   _num(s.get("pChange")),
                "volume":      s.get("totalTradedVolume") or s.get("quantityTraded"),
                "vwap":        _num(s.get("vwap")),
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
    type_label = "Sectoral Indices" if type.lower() == "sectoral" else "Broad Market Indices"
    url = f"{STOCKS_BASE}?type={quote(type_label)}&indices={quote(index_name.upper())}"
    try:
        return {"url": url, "data": await _nse_get(url)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
