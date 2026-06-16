from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas do .env."""

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"

    app_host: str = "0.0.0.0"
    app_port: int = 6060

    data_dir: str = "data"
    media_dir: str = "midia"
    catalog_dir: str = "catalogos"
    database_path: str = "atendente.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
