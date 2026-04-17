"""High-level Kotak Neo service wrapping auth + WebSocket feed management."""
import asyncio
import json
from typing import Set

from fastapi import WebSocket
from neo_api_client import NeoAPI

from app.core.auth.kotak_neo import kotak_auth
from app.core.config import settings


class KotakService:
    def __init__(self):
        self._subscribers: Set[WebSocket] = set()
        self._feed_active = False

    async def init(self):
        """Called at app startup. Skips auth if credentials are not configured."""
        if not settings.kotak_neo_consumer_key:
            return
        try:
            await kotak_auth.get_client()
            print("[KotakService] Authenticated successfully")
        except Exception as e:
            print(f"[KotakService] Auth skipped at startup: {e}")

    async def get_client(self) -> NeoAPI:
        return await kotak_auth.get_client()

    async def close(self):
        self._feed_active = False
        await kotak_auth.close()

    # ── WebSocket fan-out ─────────────────────────────────────────────────────

    async def subscribe_websocket(self, ws: WebSocket):
        self._subscribers.add(ws)

    async def unsubscribe_websocket(self, ws: WebSocket):
        self._subscribers.discard(ws)

    async def _broadcast(self, payload: dict):
        dead = set()
        for ws in self._subscribers:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        self._subscribers -= dead

    def on_tick(self, message):
        """Kotak Neo WebSocket callback — fan out to all frontend clients."""
        asyncio.create_task(self._broadcast({"type": "tick", "data": message}))


kotak_service = KotakService()
