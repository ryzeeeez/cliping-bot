"""Instrumentation placeholder."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from .logging import get_logger

logger = get_logger(__name__)


@contextmanager
def track_span(name: str, **kwargs) -> Iterator[None]:
    logger.info("span.start", span=name, **kwargs)
    try:
        yield
    finally:
        logger.info("span.end", span=name, **kwargs)
