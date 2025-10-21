"""Constantes globales pour Cliping Bot."""

from __future__ import annotations

from enum import Enum


class JobPhase(str, Enum):
    """Phases de traitement d'un job."""

    ANALYSE = "analysis"
    AUTO_PICK = "auto_pick"
    SUBTITLES = "subtitles"
    EXPORT = "export"
    DELIVERY = "delivery"


PHASE_WEIGHTS: dict[JobPhase, tuple[int, int]] = {
    JobPhase.ANALYSE: (0, 10),
    JobPhase.AUTO_PICK: (10, 30),
    JobPhase.SUBTITLES: (30, 60),
    JobPhase.EXPORT: (60, 90),
    JobPhase.DELIVERY: (90, 100),
}


class ClipFormat(str, Enum):
    TIKTOK = "tiktok"
    SQUARE = "square"
    YOUTUBE = "youtube"


FORMAT_RESOLUTIONS: dict[ClipFormat, tuple[int, int]] = {
    ClipFormat.TIKTOK: (1080, 1920),
    ClipFormat.SQUARE: (1080, 1080),
    ClipFormat.YOUTUBE: (1920, 1080),
}


class SubscriptionPlan(str, Enum):
    FREE = "free"
    PRO = "pro"


DEFAULT_INTRO_OUTRO_SKIP = 5
DEFAULT_CLIP_COUNT = 3
DEFAULT_CLIP_DURATION = 30
MAX_FREE_CLIP_DURATION = 60
MAX_PRO_CLIP_DURATION = 120
MAX_CLIPS_FREE = 3
MAX_CLIPS_PRO = 10

STATUS_UPDATE_INTERVAL_SECONDS = 2.5
PROGRESS_STALL_WARNING_SECONDS = 60
