import asyncio
import logging
import time
import httpx
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import quote

router = APIRouter()
logger = logging.getLogger("tradeos.nse")

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Origin": "https://www.nseindia.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "DNT": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

HEATMAP_URLS = {
    "sectoral": "https://www.nseindia.com/api/heatmap-index?type=Sectoral%20Indices",
    "broad":    "https://www.nseindia.com/api/heatmap-index?type=Broad%20Market%20Indices",
}
STOCKS_BASE = "https://www.nseindia.com/api/heatmap-symbols"

# Persistent client — keeps cookies alive between calls
_client: httpx.AsyncClient | None = None
_client_lock: asyncio.Lock | None = None
_session_ready = False

# Simple TTL cache {url: (timestamp, data)}
_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 30  # seconds


def _get_lock() -> asyncio.Lock:
    """Lazily create the lock inside the running event loop."""
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


async def _init_session(client: httpx.AsyncClient) -> None:
    """Visit homepage + market data page to collect NSE cookies."""
    for path in ("/", "/market-data/live-equity-market"):
        try:
            await client.get(f"{NSE_BASE}{path}")
            await asyncio.sleep(0.3)
        except Exception as exc:  # noqa: BLE001
            logger.debug("NSE warm-up %s skipped: %s", path, exc)


async def _get_client() -> httpx.AsyncClient:
    global _client, _session_ready
    lock = _get_lock()
    if _client is not None and not _client.is_closed:
        return _client
    async with lock:
        if _client is not None and not _client.is_closed:
            return _client
        logger.info("Creating new NSE session...")
        _client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=NSE_HEADERS,
        )
        await _init_session(_client)
        _session_ready = True
        logger.info("NSE session ready")
        return _client


async def _nse_get(url: str, max_retries: int = 2) -> object:
    """Fetch URL from NSE with retry and session-refresh on 403."""
    # Check cache first
    cached = _cache.get(url)
    if cached and (time.monotonic() - cached[0]) < CACHE_TTL:
        return cached[1]

    global _client
    for attempt in range(max_retries + 1):
        client = await _get_client()
        try:
            resp = await client.get(url)
            if resp.status_code == 403:
                logger.warning("NSE 403 on attempt %d — refreshing session", attempt + 1)
                # Force new session
                try:
                    await _client.aclose()
                except Exception:
                    pass
                _client = None
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                raise httpx.HTTPStatusError(
                    "NSE returned 403", request=resp.request, response=resp
                )
            resp.raise_for_status()
            data = resp.json()
            _cache[url] = (time.monotonic(), data)
            return data
        except httpx.HTTPStatusError:
            raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            logger.warning("NSE network error attempt %d: %s", attempt + 1, exc)
            try:
                await _client.aclose()
            except Exception:
                pass
            _client = None
            if attempt == max_retries:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError("NSE request failed after retries")


def _num(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _parse_index(idx: dict) -> dict:
    current = _num(
        idx.get("current") or idx.get("last") or
        idx.get("lastPrice") or idx.get("indexValue")
    )
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


# ── Heatmap ────────────────────────────────────────────────────────────────

@router.get("/heatmap")
async def sector_heatmap(type: str = Query(default="sectoral")):
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        data = await _nse_get(url)
        raw = data if isinstance(data, list) else data.get("data", [])
        sectors = [
            _parse_index(i) for i in raw
            if i.get("index") or i.get("indexSymbol") or i.get("name")
        ]
        return {"sectors": sectors, "count": len(sectors)}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE returned {e.response.status_code}")
    except Exception as e:
        logger.error("heatmap error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap/raw")
async def heatmap_raw(type: str = Query(default="sectoral")):
    url = HEATMAP_URLS.get(type.lower(), HEATMAP_URLS["sectoral"])
    try:
        return {"url": url, "data": await _nse_get(url)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sector stocks ──────────────────────────────────────────────────────────

@router.get("/sector/{index_name}")
async def sector_stocks(
    index_name: str,
    type: str = Query(default="sectoral"),
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
        logger.error("sector_stocks error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector/{index_name}/raw")
async def sector_stocks_raw(index_name: str, type: str = Query(default="sectoral")):
    type_label = "Sectoral Indices" if type.lower() == "sectoral" else "Broad Market Indices"
    url = f"{STOCKS_BASE}?type={quote(type_label)}&indices={quote(index_name.upper())}"
    try:
        return {"url": url, "data": await _nse_get(url)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Scrip search & quote ───────────────────────────────────────────────────

@router.get("/search")
async def search_scrip(q: str = Query(..., min_length=1)):
    url = f"{NSE_BASE}/api/search/autocomplete?q={quote(q)}"
    try:
        raw = await _nse_get(url)
        symbols = raw.get("symbols", [])
        results = [
            {
                "symbol": s.get("symbol") or s.get("nsecode"),
                "name":   s.get("company") or s.get("companyName") or "",
                "series": s.get("series", "EQ"),
            }
            for s in symbols
            if s.get("symbol") or s.get("nsecode")
        ]
        return {"results": results[:20]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote")
async def equity_quote(symbol: str = Query(...)):
    url = f"{NSE_BASE}/api/quote-equity?symbol={quote(symbol.upper())}"
    try:
        raw = await _nse_get(url)
        price = raw.get("priceInfo", {})
        intra = price.get("intraDayHighLow", {})
        return {
            "symbol":    symbol.upper(),
            "lastPrice": _num(price.get("lastPrice")),
            "pctChange": _num(price.get("pChange")),
            "change":    _num(price.get("change")),
            "open":      _num(price.get("open")),
            "high":      _num(intra.get("max") or price.get("high")),
            "low":       _num(intra.get("min") or price.get("low")),
            "close":     _num(price.get("previousClose")),
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NSE {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Option chain ───────────────────────────────────────────────────────────

@router.get("/option-chain")
async def option_chain(
    symbol: str = Query(...),
    type: str = Query(default="index"),
):
    endpoint = "option-chain-indices" if type.lower() == "index" else "option-chain-equities"
    url = f"{NSE_BASE}/api/{endpoint}?symbol={quote(symbol.upper())}"
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
