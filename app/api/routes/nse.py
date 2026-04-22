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
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


async def _nse_get(url: str):
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
        r = await client.get(url, headers=NSE_HEADERS)
        r.raise_for_status()
        return r.json()


def _parse_index(idx: dict) -> dict:
    # NSE heatmap-index uses: index, current, close, pChange, open, high, low
    current = _num(idx.get("current") or idx.get("last") or idx.get("lastPrice") or idx.get("indexValue"))
    prev_close = _num(idx.get("close") or idx.get("previousClose"))
    change = _num(idx.get("variation") or idx.get("change") or idx.get("netChange"))
    if change == 0.0 and current != 0.0 and prev_close != 0.0:
        change = round(current - prev_close, 2)
    return {
        "name":      idx.get("index") or idx.get("indexSymbol") or idx.get("name") or "",
        "last":      current,
        "change":    change,
        "pctChange": _num(idx.get("pChange") or idx.get("percentChange") or idx.get("perChange")),
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
        sectors = [_parse_index(i) for i in raw if i.get("index") or i.get("indexSymbol") or i.get("name")]
        return {"sectors": sectors, "count": len(sectors)}
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
        return {"index": index_name.upper(), "stocks": stocks, "count": len(stocks)}
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


@router.get("/option-chain")
async def option_chain(
    symbol: str = Query(..., description="NIFTY, BANKNIFTY, FINNIFTY, HDFCBANK, etc."),
    type: str = Query(default="index", description="index | equity"),
):
    """Proxy NSE option chain. Returns expiry dates, spot value, and per-strike CE/PE data."""
    endpoint = "option-chain-indices" if type.lower() == "index" else "option-chain-equities"
    url = f"https://www.nseindia.com/api/{endpoint}?symbol={quote(symbol.upper())}"
    try:
        raw = await _nse_get(url)
        records = raw.get("records", {})
        data = records.get("data", [])
        parsed = []
        for row in data:
            item: dict = {
                "strikePrice": row.get("strikePrice"),
                "expiryDate":  row.get("expiryDate"),
            }
            for ot in ("CE", "PE"):
                if ot in row:
                    o = row[ot]
                    item[ot] = {
                        "lastPrice": _num(o.get("lastPrice")),
                        "change":    _num(o.get("change")),
                        "pChange":   _num(o.get("pChange")),
                        "oi":        int(o.get("openInterest") or 0),
                        "volume":    int(o.get("totalTradedVolume") or 0),
                        "iv":        _num(o.get("impliedVolatility")),
                    }
            parsed.append(item)
        return {
            "symbol":          symbol.upper(),
            "underlyingValue": _num(records.get("underlyingValue")),
            "expiryDates":     records.get("expiryDates", []),
            "timestamp":       records.get("timestamp"),
            "data":            parsed,
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
