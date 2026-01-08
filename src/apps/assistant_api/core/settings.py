from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Homework Helper API"
    log_level: str = "INFO"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    cache_ttl_seconds: int = 300

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)


def load_settings() -> Settings:
    return Settings()
