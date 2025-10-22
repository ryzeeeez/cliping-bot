"""Génération des claviers inline."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from ..const import StorageMode
from ..services.presets import PRESETS
from ..services.telegram import (
    build_settings_keyboard,
    build_start_keyboard,
    build_status_keyboard,
)


def start_keyboard(pro_mode_enabled: bool, storage_mode: StorageMode) -> InlineKeyboardMarkup:
    presets = [(preset.emoji, preset.name) for preset in PRESETS]
    return build_start_keyboard(presets, pro_mode_enabled, storage_mode)


def status_keyboard(job_id: str, show_details: bool, is_pro: bool) -> InlineKeyboardMarkup:
    return build_status_keyboard(job_id, show_details, is_pro)


def settings_keyboard(storage_mode: StorageMode) -> InlineKeyboardMarkup:
    return build_settings_keyboard(storage_mode)
