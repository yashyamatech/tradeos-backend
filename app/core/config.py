from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_env: str = "development"
    allowed_origins: List[str] = ["http://localhost:3000"]

    # Kotak Neo
    kotak_neo_consumer_key: str = ""
    kotak_neo_mobile_number: str = ""
    kotak_neo_ucc: str = ""
    kotak_neo_mpin: str = ""
    kotak_neo_totp_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
