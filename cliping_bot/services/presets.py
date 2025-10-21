"""Catalogue des presets 1-clic."""

from __future__ import annotations

from . import plans
from ..const import ClipFormat
from ..models import ClipOptions, Preset


PRESETS: list[Preset] = [
    Preset(
        name="Auto TikTok (3×30s)",
        description="3 clips dynamiques de 30 s, format 9:16, sous-titres automatiques.",
        emoji="🎯",
        options=ClipOptions(
            clips=3,
            duration=30,
            format=ClipFormat.TIKTOK,
            subs="auto",
            music_ducking=False,
            intro_outro_skip=5,
            ai_pick=True,
            diversite_clips=True,
            safe_faces_text=True,
        ),
    ),
    Preset(
        name="Auto TikTok (1×60s)",
        description="Un highlight long (60 s) en 9:16 avec sous-titres auto.",
        emoji="🚀",
        options=ClipOptions(
            clips=1,
            duration=60,
            format=ClipFormat.TIKTOK,
            subs="auto",
            intro_outro_skip=5,
            ai_pick=True,
            diversite_clips=True,
        ),
    ),
    Preset(
        name="Auto YouTube (1×60s)",
        description="Clip paysage 16:9 sans sous-titres, idéal Shorts/YouTube.",
        emoji="▶️",
        options=ClipOptions(
            clips=1,
            duration=60,
            format=ClipFormat.YOUTUBE,
            subs="off",
            intro_outro_skip=5,
            ai_pick=True,
            diversite_clips=True,
        ),
    ),
    Preset(
        name="Podcast (3×45s + subs)",
        description="Découpage podcast avec diarisation A/B, ducking musical.",
        emoji="🎙️",
        options=ClipOptions(
            clips=3,
            duration=45,
            format=ClipFormat.TIKTOK,
            subs="on",
            music_ducking=True,
            intro_outro_skip=3,
            ai_pick=True,
            diversite_clips=True,
        ),
    ),
    Preset(
        name="Manuel assisté",
        description="Découpe guidée par boutons et aperçu 10 s.",
        emoji="✂️",
        options=ClipOptions(
            clips=3,
            duration=30,
            format=ClipFormat.TIKTOK,
            subs="auto",
            intro_outro_skip=5,
            ai_pick=False,
            diversite_clips=False,
        ),
    ),
]


def get_default_preset() -> Preset:
    return PRESETS[0]


def get_preset_by_name(name: str) -> Preset | None:
    for preset in PRESETS:
        if preset.name == name:
            return preset
    return None


__all__ = ["PRESETS", "get_default_preset", "get_preset_by_name"]
