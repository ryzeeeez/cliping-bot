"""Initialisation des logs structurés."""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    import structlog  # type: ignore
except ImportError:  # pragma: no cover - fallback pour les tests sans structlog
    structlog = None


class SimpleLogger:
    """Fallback minimal compatible avec l'API structlog utilisée dans le projet."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._context: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> "SimpleLogger":
        new_logger = SimpleLogger(self._logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        payload = {**self._context, **kwargs}
        if payload:
            self._logger.log(level, "%s %s", event, payload)
        else:
            self._logger.log(level, "%s", event)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure `structlog` et le logging standard."""

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)
    if structlog is None:
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )


def get_logger(*args: Any, **kwargs: Any):
    """Helper pour créer un logger structlog."""

    if structlog is None:
        name = args[0] if args else __name__
        return SimpleLogger(str(name))
    return structlog.get_logger(*args, **kwargs)
