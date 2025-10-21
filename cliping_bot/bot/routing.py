"""Construction de l'application Telegram."""

from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder

from ..config import get_settings
from ..logging import configure_logging
from .handlers import HANDLERS


def build_application() -> Application:
    settings = get_settings()
    configure_logging()
    builder = ApplicationBuilder().token(settings.telegram_token)
    app = builder.build()
    for handler in HANDLERS:
        app.add_handler(handler)
    return app
