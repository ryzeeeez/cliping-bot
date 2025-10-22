"""Point d'entrée du bot."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .bot.routing import build_router
from .config import get_settings
from .logging import configure_logging
from .services.prerequisites import ensure_prerequisites


async def main() -> None:
    settings = get_settings()
    configure_logging()
    await ensure_prerequisites()

    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_router())

    await dp.start_polling(bot)


if __name__ == "__main__":  # pragma: no cover - exécution directe
    asyncio.run(main())
