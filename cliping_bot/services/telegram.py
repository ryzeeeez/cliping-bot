"""Helpers d'intégration Telegram spécifiques."""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


MUTE_CALLBACK = "mute"
DETAILS_CALLBACK = "details"
PRIORITY_CALLBACK = "priority"
CANCEL_CALLBACK = "cancel"


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


def build_start_keyboard(presets: list[tuple[str, str]], pro_mode_enabled: bool) -> InlineKeyboardMarkup:
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
    return InlineKeyboardMarkup(rows)
