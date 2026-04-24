import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger("tradeos")


class Settings(BaseSettings):
    app_env: str = "development"
    allowed_origins: str = "*"
    backend_api_key: str = ""
    database_url: str = ""

    # Kotak Neo
    kotak_neo_consumer_key: str = ""
    kotak_neo_mobile_number: str = ""
    kotak_neo_ucc: str = ""
    kotak_neo_mpin: str = ""
    kotak_neo_totp_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_origins(self) -> list[str]:
        origins = [o.strip() for o in self.allowed_origins.split(",")]
        if self.app_env == "production" and "*" in origins:
            logger.warning(
                "SECURITY: ALLOWED_ORIGINS is '*' in production. "
                "Set ALLOWED_ORIGINS to your Vercel URL in Railway env vars."
            )
        return origins

    @property
    def async_db_url(self) -> str:
        """Convert Railway DATABASE_URL to asyncpg-compatible URL.
        Railway may provide either postgres:// or postgresql://.
        """
        url = self.database_url
        # Normalise postgres:// -> postgresql://
        if url.startswith("postgres://"):
            url = "postgresql" + url[len("postgres"):]
        # Inject asyncpg driver
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)


settings = Settings()
