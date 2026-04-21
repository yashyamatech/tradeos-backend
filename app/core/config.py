from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    allowed_origins: str = "*"
    backend_api_key: str = ""

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
            raise ValueError("Wildcard ALLOWED_ORIGINS is not permitted in production")
        return origins


settings = Settings()
