"""Kotak Neo API v2 authentication and session management.

Auth flow (two steps, both synchronous under the hood):
  1. totp_login(mobile_number, ucc, totp)  → view token + session id
  2. totp_validate(mpin)                   → trade token (required for orders)

The client is re-authenticated once per calendar day and cached as a
module-level singleton via `kotak_auth.get_client()`.
"""
import pyotp
import asyncio
from typing import Optional
from datetime import date

from neo_api_client import NeoAPI

from app.core.config import settings


class KotakNeoAuth:
    def __init__(self):
        self._client: Optional[NeoAPI] = None
        self._auth_date: Optional[date] = None
        self._lock = asyncio.Lock()

    def _make_totp(self) -> str:
        return pyotp.TOTP(settings.kotak_neo_totp_secret).now()

    async def _authenticate(self) -> NeoAPI:
        client = NeoAPI(
            environment="prod",
            access_token=None,
            neo_fin_key=None,
            consumer_key=settings.kotak_neo_consumer_key,
        )

        # Step 1: TOTP login — generates view token + session id
        login_resp = await asyncio.to_thread(
            client.totp_login,
            mobile_number=settings.kotak_neo_mobile_number,
            ucc=settings.kotak_neo_ucc,
            totp=self._make_totp(),
        )
        if not login_resp or login_resp.get("data") is None:
            raise RuntimeError(f"totp_login failed: {login_resp}")

        # Step 2: TOTP validate — generates trade token
        validate_resp = await asyncio.to_thread(
            client.totp_validate,
            mpin=settings.kotak_neo_mpin,
        )
        if not validate_resp or validate_resp.get("data") is None:
            raise RuntimeError(f"totp_validate failed: {validate_resp}")

        return client

    async def get_client(self) -> NeoAPI:
        """Return a valid authenticated NeoAPI client, re-authing once per day."""
        async with self._lock:
            today = date.today()
            if self._client is None or self._auth_date != today:
                self._client = await self._authenticate()
                self._auth_date = today
        return self._client

    async def close(self):
        if self._client:
            try:
                await asyncio.to_thread(self._client.logout)
            except Exception:
                pass
        self._client = None
        self._auth_date = None

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None and self._auth_date == date.today()


kotak_auth = KotakNeoAuth()
