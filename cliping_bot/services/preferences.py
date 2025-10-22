"""Gestion simple des préférences utilisateur (stockage, qualité, etc.)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..const import StorageMode
from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class UserPreferences:
    storage_mode: StorageMode


class PreferencesStore:
    """Persistance JSON minimale pour les préférences utilisateur."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".clipingbot_prefs.json"
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - log seulement
            logger.warning("prefs.load_failed", error=str(exc))
            return
        if isinstance(raw, dict):
            self._data = raw

    async def get(self, user_id: int, fallback: StorageMode) -> UserPreferences:
        async with self._lock:
            entry = self._data.get(str(user_id), {})
        storage = entry.get("storage_mode")
        try:
            storage_mode = StorageMode(storage) if storage else fallback
        except ValueError:
            storage_mode = fallback
        return UserPreferences(storage_mode=storage_mode)

    async def set_storage_mode(self, user_id: int, mode: StorageMode) -> None:
        async with self._lock:
            entry = self._data.setdefault(str(user_id), {})
            entry["storage_mode"] = mode.value
            await self._persist_locked()

    async def _persist_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._data), encoding="utf-8")
        tmp_path.replace(self.path)


_store: PreferencesStore | None = None


def get_preferences_store() -> PreferencesStore:
    global _store
    if _store is None:
        _store = PreferencesStore()
    return _store

