"""Kotak Neo REST authentication using httpx — no SDK dependency.

Auth flow (two sequential POST requests):
  Step 1 — totp/login   : mobile + ucc + totp  → view_token + sid
  Step 2 — totp/validate: mpin                 → trade_token + sid

The authenticated session is cached for the calendar day and refreshed
automatically on the next request after midnight.
"""
import asyncio
import pyotp
import httpx
from datetime import date
from typing import Optional

from app.core.config import settings

BASE_URL = "https://gw-napi.kotaksecurities.com"
NEO_FIN_KEY = "neotradeapi"


class KotakSession:
    __slots__ = ("trade_token", "sid", "rid", "hs_server_id")

    def __init__(self, trade_token: str, sid: str, rid: str, hs_server_id: str):
        self.trade_token = trade_token
        self.sid = sid
        self.rid = rid
        self.hs_server_id = hs_server_id


class KotakNeoAuth:
    def __init__(self):
        self._session: Optional[KotakSession] = None
        self._auth_date: Optional[date] = None
        self._lock = asyncio.Lock()

    def _make_totp(self) -> str:
        return pyotp.TOTP(settings.kotak_neo_totp_secret).now()

    async def _authenticate(self) -> KotakSession:
        async with httpx.AsyncClient(timeout=15) as client:
            # ─ Step 1: TOTP login ───────────────────────────────────────────
            r1 = await client.post(
                f"{BASE_URL}/login/1.0/login/v6/totp/login",
                headers={
                    "Authorization": settings.kotak_neo_consumer_key,
                    "neo-fin-key": NEO_FIN_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "mobileNumber": settings.kotak_neo_mobile_number,
                    "ucc": settings.kotak_neo_ucc,
                    "totp": self._make_totp(),
                },
            )
            r1.raise_for_status()
            d1 = r1.json()

            try:
                view_token = d1["data"]["token"]
                sid = d1["data"]["sid"]
            except (KeyError, TypeError) as e:
                raise RuntimeError(f"totp/login unexpected response: {d1}") from e

            # ─ Step 2: TOTP validate ──────────────────────────────────────
            r2 = await client.post(
                f"{BASE_URL}/login/1.0/login/v6/totp/validate",
                headers={
                    "Authorization": settings.kotak_neo_consumer_key,
                    "sid": sid,
                    "Auth": view_token,
                    "neo-fin-key": NEO_FIN_KEY,
                    "Content-Type": "application/json",
                },
                json={"mpin": settings.kotak_neo_mpin},
            )
            r2.raise_for_status()
            d2 = r2.json()

            try:
                trade_token = d2["data"]["token"]
                sid2 = d2["data"]["sid"]
                rid = d2["data"].get("rid", "")
                hs_server_id = d2["data"].get("hsServerId", "")
            except (KeyError, TypeError) as e:
                raise RuntimeError(f"totp/validate unexpected response: {d2}") from e

        return KotakSession(
            trade_token=trade_token,
            sid=sid2,
            rid=rid,
            hs_server_id=hs_server_id,
        )

    async def get_session(self) -> KotakSession:
        """Return a valid session, re-authenticating once per calendar day."""
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
