"""Point d'entrée du bot."""

from __future__ import annotations

import asyncio

from .bot.routing import build_application


async def main() -> None:
    app = build_application()
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try:
        await app.updater.wait_until_finished()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":  # pragma: no cover - exécution directe
    asyncio.run(main())
