"""Thin wrapper around kotak_auth exposing session to the rest of the app."""
from app.core.auth.kotak_neo import kotak_auth, KotakSession
from app.core.config import settings


class KotakService:
    async def init(self):
        if not settings.kotak_neo_consumer_key:
            print("[KotakService] No credentials — skipping startup auth")
            return
        try:
            await kotak_auth.get_session()
            print("[KotakService] Authenticated successfully")
        except Exception as e:
            print(f"[KotakService] Startup auth failed (will retry on demand): {e}")

    async def get_session(self) -> KotakSession:
        return await kotak_auth.get_session()

    async def close(self):
        await kotak_auth.close()


kotak_service = KotakService()
