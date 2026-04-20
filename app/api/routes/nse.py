import httpx
from fastapi import APIRouter, HTTPException

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


@router.get("/heatmap")
async def sector_heatmap():
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Establish NSE session (required for cookie)
            await client.get("https://www.nseindia.com", headers=NSE_HEADERS)

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
        raise HTTPException(status_code=502, detail=f"NSE error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices")
async def all_indices():
    """Returns all NSE indices — useful for debugging raw response."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com", headers=NSE_HEADERS)
            r = await client.get("https://www.nseindia.com/api/allIndices", headers=NSE_HEADERS)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
