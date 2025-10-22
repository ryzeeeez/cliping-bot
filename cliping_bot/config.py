"""Gestion centralisée de la configuration du bot."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseSettings, Field, HttpUrl, validator

from .const import StorageMode


class Settings(BaseSettings):
    """Paramètres chargés via variables d'environnement (avec défauts intelligents)."""

    bot_token: str | None = Field(None, alias="BOT_TOKEN")
    legacy_telegram_token: str | None = Field(None, alias="TELEGRAM_TOKEN")
    telegram_mode: Literal["polling", "webhook"] = Field("polling", alias="TELEGRAM_MODE")
    telegram_webhook_url: HttpUrl | None = Field(None, alias="TELEGRAM_WEBHOOK_URL")
    telegram_webhook_secret: str | None = Field(None, alias="TELEGRAM_WEBHOOK_SECRET")

    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    tasks_api_url: HttpUrl = Field("https://tasks.invalid", alias="TASKS_API_URL")

    storage_mode: str = Field(StorageMode.LOCAL.value, alias="STORAGE_MODE")
    local_output_dir: str = Field("~/Downloads/Clips_TMP", alias="LOCAL_OUTPUT_DIR")
    local_retention_min: int = Field(60, alias="LOCAL_RETENTION_MIN")
    local_delete_on_complete: bool = Field(True, alias="LOCAL_DELETE_ON_COMPLETE")
    external_volume_path: str | None = Field(None, alias="EXTERNAL_VOLUME_PATH")
    use_ramdisk: bool = Field(False, alias="USE_RAMDISK")
    ramdisk_size_mb: int = Field(4096, alias="RAMDISK_SIZE_MB")

    storage_provider: str = Field("s3", alias="STORAGE_PROVIDER")
    s3_endpoint: HttpUrl | None = Field("https://s3.example.com", alias="S3_ENDPOINT")
    s3_region: str | None = Field("us-east-1", alias="S3_REGION")
    s3_bucket: str | None = Field("cliping", alias="S3_BUCKET")
    s3_access_key_id: str | None = Field("test-access", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field("test-secret", alias="S3_SECRET_ACCESS_KEY")
    storage_ttl_hours: int = Field(24, alias="STORAGE_TTL_HOURS")

    environment: Literal["dev", "staging", "prod"] = Field("dev", alias="ENVIRONMENT")
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")

    free_daily_quota: int = Field(5, alias="FREE_DAILY_QUOTA")
    pro_daily_quota: int = Field(50, alias="PRO_DAILY_QUOTA")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    @validator("bot_token", always=True)
    def _ensure_token(cls, value: str | None, values: dict[str, Any]) -> str:  # noqa: D417
        legacy = values.get("legacy_telegram_token")
        token = value or legacy
        if not token:
            raise ValueError("BOT_TOKEN manquant. Ajoute-le dans ton fichier .env.")
        return token

    @validator("admin_user_ids", pre=True)
    def _split_admin_ids(cls, value: str | list[int]) -> list[int]:  # noqa: D417 - docstring inutile
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(v.strip()) for v in value.split(",") if v.strip()]

    @property
    def telegram_token(self) -> str:
        return self.bot_token  # compat

    @property
    def storage_mode_enum(self) -> StorageMode:
        try:
            return StorageMode(self.storage_mode)
        except ValueError:
            return StorageMode.LOCAL

    @property
    def resolved_local_output_dir(self) -> Path:
        return Path(self.local_output_dir).expanduser()

    @property
    def resolved_external_volume(self) -> Path | None:
        if not self.external_volume_path:
            return None
        return Path(self.external_volume_path).expanduser()


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de configuration."""

    return Settings()
