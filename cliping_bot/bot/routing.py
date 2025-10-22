"""Construction du routeur aiogram."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Router

from ..config import get_settings
from ..const import StorageMode
from ..logging import get_logger
from ..services.storage import get_storage_coordinator
from .handlers import router as handlers_router

logger = get_logger(__name__)


def build_router() -> Router:
    settings = get_settings()
    coordinator = get_storage_coordinator()
    main_router = Router()
    main_router.include_router(handlers_router)

    async def _startup(_: Bot) -> None:
        if settings.storage_mode_enum is StorageMode.LOCAL or settings.use_ramdisk:
            interval = max(60, settings.local_retention_min * 30)

            async def _purge_loop() -> None:
                while True:
                    try:
                        await coordinator.purge_expired()
                    except Exception as exc:  # pragma: no cover - journalisation seulement
                        logger.warning("storage.purge_failed", error=str(exc))
                    await asyncio.sleep(interval)

            main_router.data["purge_task"] = asyncio.create_task(_purge_loop())

    async def _shutdown(_: Bot) -> None:
        task = main_router.data.get("purge_task")
        if task:
            task.cancel()

    main_router.startup.register(_startup)
    main_router.shutdown.register(_shutdown)
    return main_router
