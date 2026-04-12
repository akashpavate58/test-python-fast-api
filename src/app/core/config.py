from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_name: str = "FastAPI Service"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    allowed_cors_origins: str | list[str] = []
    azuresql_connection_string: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    external_api_base_url: str = ""
    external_api_timeout_seconds: int = 10

    @field_validator("allowed_cors_origins", mode="before")
    @classmethod
    def _normalize_allowed_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
