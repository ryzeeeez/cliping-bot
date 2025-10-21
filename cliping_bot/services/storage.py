"""Abstraction de stockage éphémère via API compatible S3."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import get_settings
from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class PreSignedUrl:
    url: str
    expires_at: float

    def as_dict(self) -> dict[str, Any]:
        return {"url": self.url, "expires_at": self.expires_at}


class EphemeralStorageClient:
    """Client simple pour générer des URLs pré-signées via un service custom."""

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint = str(settings.storage_endpoint)
        self.bucket = settings.storage_bucket
        self._http = httpx.AsyncClient(base_url=self.endpoint, timeout=30)
        self._key = settings.storage_key.encode()
        self._secret = settings.storage_secret.encode()

    async def __aenter__(self) -> "EphemeralStorageClient":  # pragma: no cover - sugar syntax
        return self

    async def __aexit__(self, *exc: object) -> None:  # pragma: no cover
        await self._http.aclose()

    async def create_upload_url(self, object_name: str, ttl_seconds: int = 3600) -> PreSignedUrl:
        payload = {
            "bucket": self.bucket,
            "object": object_name,
            "ttl": ttl_seconds,
        }
        signature = self._sign(payload)
        response = await self._http.post("/presign", json={**payload, "signature": signature})
        response.raise_for_status()
        data = response.json()
        return PreSignedUrl(url=data["url"], expires_at=time.time() + ttl_seconds)

    async def delete_object(self, object_name: str) -> None:
        try:
            response = await self._http.delete(f"/objects/{self.bucket}/{object_name}")
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - log only
            logger.warning("storage.delete_failed", object=object_name, error=str(exc))

    def _sign(self, payload: dict[str, Any]) -> str:
        digest = hmac.new(self._secret, repr(sorted(payload.items())).encode(), hashlib.sha256).hexdigest()
        return digest


async def with_storage_client(func, *args, **kwargs):
    async with EphemeralStorageClient() as client:
        return await func(client, *args, **kwargs)
