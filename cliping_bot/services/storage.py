"""Gestion des modes de stockage (local et cloud)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - autorise les tests sans dépendances cloud
    httpx = None

from ..config import Settings, get_settings
from ..const import StorageMode
from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class StorageAllocation:
    """Représente la configuration de stockage retenue pour un job."""

    job_id: str
    mode: StorageMode
    base_path: Path | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalStorageManager:
    """Orchestre l'écriture locale (dossier, volume externe ou RAM disk)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._ramdisk_path: Path | None = None
        self._lock = asyncio.Lock()
        self._tracked_jobs: dict[str, Path] = {}

    async def ensure_ready(self) -> None:
        """Valide et prépare le dossier cible au démarrage."""

        async with self._lock:
            root, warnings = await self._resolve_base_path()
            if warnings:
                for warning in warnings:
                    logger.warning("storage.local_warning", warning=warning)
            logger.info("storage.local_ready", path=str(root))
        await self.purge_expired()

    async def allocate(self, job_id: str) -> StorageAllocation:
        async with self._lock:
            base_path, warnings = await self._resolve_base_path()
            job_path = base_path / job_id
            job_path.mkdir(parents=True, exist_ok=True)
            self._tracked_jobs[job_id] = job_path
            return StorageAllocation(
                job_id=job_id,
                mode=StorageMode.LOCAL,
                base_path=job_path,
                warnings=warnings,
            )

    async def cleanup(self, job_id: str, force: bool = False) -> None:
        async with self._lock:
            path = self._tracked_jobs.pop(job_id, None)
        if not path:
            return
        if not self.settings.local_delete_on_complete and not force:
            return
        await self._remove_path(path)
        await self._teardown_ramdisk_if_unused()

    async def purge_expired(self) -> list[Path]:
        """Supprime les dossiers plus vieux que la rétention configurée."""

        cutoff = datetime.utcnow() - timedelta(minutes=self.settings.local_retention_min)
        removed: list[Path] = []
        for root in await self._candidate_roots():
            if not root.exists():
                continue
            for item in root.iterdir():
                try:
                    stat = item.stat()
                except FileNotFoundError:
                    continue
                if datetime.utcfromtimestamp(stat.st_mtime) < cutoff:
                    await self._remove_path(item)
                    removed.append(item)
        if removed:
            logger.info(
                "storage.local_purge", count=len(removed), paths=[str(p) for p in removed]
            )
        await self._teardown_ramdisk_if_unused()
        return removed

    async def _resolve_base_path(self) -> tuple[Path, list[str]]:
        warnings: list[str] = []
        candidates: Iterable[Path] = []

        external = self.settings.resolved_external_volume
        if external:
            candidates = [external]
        else:
            candidates = []

        if self.settings.use_ramdisk:
            ramdisk = await self._ensure_ramdisk()
            if ramdisk:
                candidates = list(candidates) + [ramdisk]

        local = self.settings.resolved_local_output_dir
        candidates = list(candidates) + [local]

        for path in candidates:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                message = str(exc)
                if path == local:
                    raise RuntimeError(
                        "Impossible de créer le dossier local. Autorisez l'accès aux fichiers."
                    ) from exc
                warnings.append(
                    f"Impossible d'accéder à {path}: {message}. Basculade vers un support alternatif."
                )
                continue
            if not os.access(path, os.W_OK):
                warnings.append(f"Dossier {path} non inscriptible. Fallback.")
                continue
            if external and path == external and not os.path.ismount(path):
                warnings.append(
                    f"Le volume {path} n'est plus monté. Utilisation d'un stockage alternatif."
                )
                continue
            return path, warnings

        raise RuntimeError("Aucun dossier de sortie valide n'a pu être préparé.")

    async def _candidate_roots(self) -> list[Path]:
        roots: list[Path] = []
        external = self.settings.resolved_external_volume
        if external:
            roots.append(external)
        if self._ramdisk_path:
            roots.append(self._ramdisk_path)
        roots.append(self.settings.resolved_local_output_dir)
        return roots

    async def _ensure_ramdisk(self) -> Path | None:
        if self._ramdisk_path and self._ramdisk_path.exists():
            return self._ramdisk_path
        try:
            base_dir = Path(tempfile.gettempdir()) / "clipingbot_ramdisk"
            base_dir.mkdir(parents=True, exist_ok=True)
            self._ramdisk_path = base_dir
            logger.info("storage.ramdisk_ready", path=str(base_dir))
            return base_dir
        except OSError as exc:
            logger.error("storage.ramdisk_failed", error=str(exc))
            return None

    async def _remove_path(self, path: Path) -> None:
        if not path.exists():
            return
        for attempt in range(3):
            try:
                shutil.rmtree(path)
                return
            except Exception as exc:  # pragma: no cover - log + retry
                logger.warning(
                    "storage.remove_retry", path=str(path), error=str(exc), attempt=attempt + 1
                )
                await asyncio.sleep(0.5 * (attempt + 1))
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception as exc:  # pragma: no cover - dernier recours
            logger.error("storage.remove_failed", path=str(path), error=str(exc))

    async def _teardown_ramdisk_if_unused(self) -> None:
        if not self._ramdisk_path or not self.settings.use_ramdisk:
            return
        try:
            has_files = any(self._ramdisk_path.iterdir())
        except FileNotFoundError:
            self._ramdisk_path = None
            return
        if not has_files:
            await self._remove_path(self._ramdisk_path)
            self._ramdisk_path = None
            logger.info("storage.ramdisk_unmounted")


class CloudStorageClient:
    """Client simple pour les URLs pré-signées."""

    def __init__(self, settings: Settings | None = None) -> None:
        if httpx is None:
            raise RuntimeError("httpx n'est pas installé. Requis pour le mode cloud.")
        settings = settings or get_settings()
        if not settings.s3_endpoint or not settings.s3_bucket:
            raise RuntimeError("Configuration S3 incomplète.")
        self.endpoint = str(settings.s3_endpoint)
        self.bucket = settings.s3_bucket
        self._http = httpx.AsyncClient(base_url=self.endpoint, timeout=30)
        self._key = (settings.s3_access_key_id or "").encode()
        self._secret = (settings.s3_secret_access_key or "").encode()
        self._ttl_seconds = settings.storage_ttl_hours * 3600

    async def close(self) -> None:
        await self._http.aclose()

    async def create_upload_url(self, object_name: str, ttl_seconds: int | None = None) -> dict[str, Any]:
        ttl = ttl_seconds or self._ttl_seconds
        payload = {
            "bucket": self.bucket,
            "object": object_name,
            "ttl": ttl,
        }
        response = await self._http.post("/presign", json={**payload, "signature": self._sign(payload)})
        response.raise_for_status()
        data = response.json()
        data["expires_at"] = time.time() + ttl
        return data

    async def delete_object(self, object_name: str) -> None:
        try:
            response = await self._http.delete(f"/objects/{self.bucket}/{object_name}")
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover
            logger.warning("storage.cloud_delete_failed", object=object_name, error=str(exc))

    def _sign(self, payload: dict[str, Any]) -> str:
        digest = hmac.new(self._secret, repr(sorted(payload.items())).encode(), hashlib.sha256)
        return digest.hexdigest()


@asynccontextmanager
async def cloud_client(settings: Settings | None = None):
    client = CloudStorageClient(settings)
    try:
        yield client
    finally:
        await client.close()


class StorageCoordinator:
    """Expose les opérations communes pour les différents modes."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._local = LocalStorageManager(self.settings)

    async def ensure_ready(self) -> None:
        if self.settings.storage_mode_enum is StorageMode.LOCAL or self.settings.use_ramdisk:
            await self._local.ensure_ready()

    async def allocate(self, job_id: str, mode: StorageMode) -> StorageAllocation:
        if mode is StorageMode.LOCAL:
            return await self._local.allocate(job_id)
        return StorageAllocation(
            job_id=job_id,
            mode=StorageMode.CLOUD,
            metadata={"ttl_hours": self.settings.storage_ttl_hours},
        )

    async def cleanup(self, allocation: StorageAllocation, force: bool = False) -> None:
        if allocation.mode is StorageMode.LOCAL:
            await self._local.cleanup(allocation.job_id, force=force)

    async def purge_expired(self) -> list[Path]:
        return await self._local.purge_expired()


_coordinator: StorageCoordinator | None = None


def get_storage_coordinator() -> StorageCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = StorageCoordinator()
    return _coordinator

