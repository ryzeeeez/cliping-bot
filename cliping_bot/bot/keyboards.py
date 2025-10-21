"""Génération des claviers inline."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from ..services.presets import PRESETS
from ..services.telegram import build_start_keyboard, build_status_keyboard


def start_keyboard(pro_mode_enabled: bool) -> InlineKeyboardMarkup:
    presets = [(preset.emoji, preset.name) for preset in PRESETS]
    return build_start_keyboard(presets, pro_mode_enabled)


def status_keyboard(job_id: str, show_details: bool, is_pro: bool) -> InlineKeyboardMarkup:
    return build_status_keyboard(job_id, show_details, is_pro)
