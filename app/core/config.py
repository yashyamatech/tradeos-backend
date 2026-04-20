from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    allowed_origins: str = "*"

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
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
