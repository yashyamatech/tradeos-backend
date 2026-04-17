from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
import asyncio
import json

from app.services.kotak_service import kotak_service

router = APIRouter()


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """Fetch live quote for a symbol (e.g. NIFTY, BANKNIFTY)."""
    try:
        client = await kotak_service.get_client()
        quote = await asyncio.to_thread(client.quotes, instrument_tokens=[symbol], quote_type="ltp")
        return {"symbol": symbol, "data": quote}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    """WebSocket endpoint — streams live price ticks to the frontend."""
    await websocket.accept()
    try:
        # Register this websocket with the kotak_service feed manager
        await kotak_service.subscribe_websocket(websocket)
        while True:
            # Keep connection alive; data is pushed by kotak_service
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        await kotak_service.unsubscribe_websocket(websocket)
    except Exception as e:
        await kotak_service.unsubscribe_websocket(websocket)
        raise
