"""Vérifications de démarrage (binaires externes, stockage)."""

from __future__ import annotations

import shutil

from ..logging import get_logger
from .storage import get_storage_coordinator

logger = get_logger(__name__)

REQUIRED_BINARIES = ["ffmpeg", "yt-dlp"]


async def ensure_prerequisites() -> None:
    """S'assure que les prérequis essentiels sont disponibles."""

    missing = [binary for binary in REQUIRED_BINARIES if shutil.which(binary) is None]
    if missing:
        raise RuntimeError(
            " / ".join(missing)
            + " manquant(s). Installe FFmpeg et yt-dlp puis relance le bot."
        )
    coordinator = get_storage_coordinator()
    try:
        await coordinator.ensure_ready()
    except RuntimeError as exc:
        logger.error("prereq.storage_failed", error=str(exc))
        raise
