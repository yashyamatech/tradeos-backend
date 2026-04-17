from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    allowed_origins: List[str] = ["http://localhost:3000"]

    # Kotak Neo v2
    kotak_neo_consumer_key: str = ""
    kotak_neo_mobile_number: str = ""   # with country code e.g. +919876543210
    kotak_neo_ucc: str = ""             # Unique Client Code from profile
    kotak_neo_mpin: str = ""            # 6-digit MPIN
    kotak_neo_totp_secret: str = ""     # base32 seed for pyotp

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/tradeos"
    supabase_url: str = ""
    supabase_key: str = ""

    # Claude AI
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
