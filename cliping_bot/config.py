"""Gestion de la configuration via Pydantic."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseSettings, Field, HttpUrl, validator


class Settings(BaseSettings):
    telegram_token: str = Field(..., alias="TELEGRAM_TOKEN")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    tasks_api_url: HttpUrl = Field(..., alias="TASKS_API_URL")
    storage_endpoint: HttpUrl = Field(..., alias="STORAGE_ENDPOINT")
    storage_bucket: str = Field(..., alias="STORAGE_BUCKET")
    storage_key: str = Field(..., alias="STORAGE_KEY")
    storage_secret: str = Field(..., alias="STORAGE_SECRET")
    environment: Literal["dev", "staging", "prod"] = Field("dev", alias="ENVIRONMENT")
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")

    free_daily_quota: int = Field(5, alias="FREE_DAILY_QUOTA")
    pro_daily_quota: int = Field(50, alias="PRO_DAILY_QUOTA")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    @validator("admin_user_ids", pre=True)
    def _split_admin_ids(cls, value: str | list[int]) -> list[int]:  # noqa: D417 - docstring inutile
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(v.strip()) for v in value.split(",") if v.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de configuration."""

    return Settings()
