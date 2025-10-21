"""Construction de l'application Telegram."""

from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder

from ..config import get_settings
from ..const import StorageMode
from ..logging import configure_logging
from ..services.prerequisites import ensure_prerequisites
from ..services.storage import get_storage_coordinator
from .handlers import HANDLERS


def build_application() -> Application:
    settings = get_settings()
    configure_logging()
    ensure_prerequisites()
    builder = ApplicationBuilder().token(settings.telegram_token)
    app = builder.build()
    for handler in HANDLERS:
        app.add_handler(handler)
    coordinator = get_storage_coordinator()

    async def purge_callback(context):  # pragma: no cover - dépend du scheduler
        await coordinator.purge_expired()

    if settings.storage_mode_enum is StorageMode.LOCAL or settings.use_ramdisk:
        interval = max(60, settings.local_retention_min * 30)
        app.job_queue.run_repeating(purge_callback, interval=interval, first=10)
    return app
