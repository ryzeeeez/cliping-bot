"""Helpers d'intégration Telegram spécifiques."""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..const import StorageMode


MUTE_CALLBACK = "mute"
DETAILS_CALLBACK = "details"
PRIORITY_CALLBACK = "priority"
CANCEL_CALLBACK = "cancel"
SETTINGS_OPEN = "settings:open"


def _storage_label(mode: StorageMode) -> str:
    return "Local" if mode is StorageMode.LOCAL else "Cloud"


def build_status_keyboard(job_id: str, show_details: bool, is_pro: bool) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton("🔕 Mute", callback_data=f"{job_id}:{MUTE_CALLBACK}"),
        InlineKeyboardButton("📊 Détails" if not show_details else "📊 Masquer", callback_data=f"{job_id}:{DETAILS_CALLBACK}"),
        InlineKeyboardButton(
            "⏩ Priorité Pro" if not is_pro else "Pro actif",
            callback_data=f"{job_id}:{PRIORITY_CALLBACK}",
        ),
        InlineKeyboardButton("❌ Annuler", callback_data=f"{job_id}:{CANCEL_CALLBACK}"),
    ]
    return InlineKeyboardMarkup.from_row(buttons)


def build_start_keyboard(
    presets: list[tuple[str, str]], pro_mode_enabled: bool, storage_mode: StorageMode
) -> InlineKeyboardMarkup:
    rows = []
    current_row = []
    for emoji, name in presets:
        current_row.append(InlineKeyboardButton(f"{emoji} {name}", callback_data=f"preset:{name}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append(
        [
            InlineKeyboardButton(
                "⚙️ Mode Pro" if not pro_mode_enabled else "✨ Mode Simple",
                callback_data="toggle_pro",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                f"🗃️ Stockage : {_storage_label(storage_mode)}",
                callback_data=SETTINGS_OPEN,
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_settings_keyboard(storage_mode: StorageMode) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    ("✅ " if storage_mode is StorageMode.LOCAL else "") + "Local",
                    callback_data="settings:storage:local",
                ),
                InlineKeyboardButton(
                    ("✅ " if storage_mode is StorageMode.CLOUD else "") + "Cloud",
                    callback_data="settings:storage:cloud",
                ),
            ],
            [InlineKeyboardButton("Fermer", callback_data="settings:close")],
        ]
    )
