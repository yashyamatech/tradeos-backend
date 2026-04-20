"""Kotak Neo auth using the official v2 SDK."""
import asyncio
import pyotp
from datetime import date
from typing import Optional

from neo_api_client import NeoAPI

from app.core.config import settings


class KotakSession:
    __slots__ = ("client", "sid", "trade_token")

    def __init__(self, client: NeoAPI, sid: str, trade_token: str):
        self.client = client
        self.sid = sid
        self.trade_token = trade_token


class KotakNeoAuth:
    def __init__(self):
        self._session: Optional[KotakSession] = None
        self._auth_date: Optional[date] = None
        self._lock = asyncio.Lock()

    def _make_totp(self) -> str:
        return pyotp.TOTP(settings.kotak_neo_totp_secret).now()

    async def _authenticate(self) -> KotakSession:
        client = NeoAPI(
            environment="prod",
            access_token=None,
            neo_fin_key=None,
            consumer_key=settings.kotak_neo_consumer_key,
        )

        # Step 1: totp_login — returns view token + sid
        r1 = await asyncio.to_thread(
            client.totp_login,
            mobile_number=settings.kotak_neo_mobile_number,
            ucc=settings.kotak_neo_ucc,
            totp=self._make_totp(),
        )
        if not r1 or r1.get("data") is None:
            raise RuntimeError(f"totp_login failed: {r1}")

        # Step 2: totp_validate — returns trade token
        r2 = await asyncio.to_thread(
            client.totp_validate,
            mpin=settings.kotak_neo_mpin,
        )
        if not r2 or r2.get("data") is None:
            raise RuntimeError(f"totp_validate failed: {r2}")

        sid = r2["data"].get("sid", "")
        trade_token = r2["data"].get("token", "")
        return KotakSession(client=client, sid=sid, trade_token=trade_token)

    async def get_session(self) -> KotakSession:
        async with self._lock:
            today = date.today()
            if self._session is None or self._auth_date != today:
                self._session = await self._authenticate()
                self._auth_date = today
        return self._session

    async def close(self):
        self._session = None
        self._auth_date = None

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None and self._auth_date == date.today()


kotak_auth = KotakNeoAuth()
