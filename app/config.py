from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ESA WorldCover 2021 v2 API"
    database_url: str
    tile_cache_dir: Path
    tile_expiry_days: int = 365
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = 60
    session_expire_minutes: int = 60 * 24 * 7
    session_cookie_name: str = "esawc_session"
    cookie_secure: bool = False
    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_sender: str | None = None
    smtp_start_tls: bool = True
    guide_path: Path = Path("README.md")

    @model_validator(mode="after")
    def validate_smtp(self) -> Settings:
        if self.smtp_enabled and (not self.smtp_host or not self.smtp_sender):
            raise ValueError("SMTP_HOST and SMTP_SENDER are required when SMTP is enabled")
        return self

    @property
    def session_max_age_seconds(self) -> int:
        return self.session_expire_minutes * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
