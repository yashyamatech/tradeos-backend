"""Kotak Neo API authentication and session management."""
import pyotp
import asyncio
from typing import Optional
from datetime import datetime, date

from neo_api_client import NeoAPI

from app.core.config import settings


class KotakNeoAuth:
    """
    Manages a single authenticated Kotak Neo session.
    Re-authenticates automatically when the session expires (daily).
    """

    def __init__(self):
        self._client: Optional[NeoAPI] = None
        self._auth_date: Optional[date] = None
        self._lock = asyncio.Lock()

    def _generate_totp(self) -> str:
        totp = pyotp.TOTP(settings.kotak_neo_totp_secret)
        return totp.now()

    async def _authenticate(self) -> NeoAPI:
        """Perform full login flow: login → OTP (TOTP) → session."""
        client = NeoAPI(
            consumer_key=settings.kotak_neo_consumer_key,
            consumer_secret=settings.kotak_neo_consumer_secret,
            environment="prod",  # use "uat" for testing
            on_message=None,
            on_error=None,
            on_close=None,
            on_open=None,
        )

        # Step 1: initiate login with mobile + password
        login_resp = await asyncio.to_thread(
            client.login,
            mobilenumber=settings.kotak_neo_mobile_number,
            password=settings.kotak_neo_password,
        )
        if not login_resp or login_resp.get("data") is None:
            raise RuntimeError(f"Kotak Neo login failed: {login_resp}")

        # Step 2: complete OTP (TOTP-based 2FA)
        totp_code = self._generate_totp()
        otp_resp = await asyncio.to_thread(
            client.session_2fa,
            OTP=totp_code,
        )
        if not otp_resp or otp_resp.get("data") is None:
            raise RuntimeError(f"Kotak Neo 2FA failed: {otp_resp}")

        return client

    async def get_client(self) -> NeoAPI:
        """Return a valid, authenticated NeoAPI client, re-authing if needed."""
        async with self._lock:
            today = date.today()
            if self._client is None or self._auth_date != today:
                self._client = await self._authenticate()
                self._auth_date = today
        return self._client

    async def close(self):
        self._client = None
        self._auth_date = None


# Module-level singleton
kotak_auth = KotakNeoAuth()
