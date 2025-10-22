"""Handlers Telegram pour Cliping Bot."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from telegram import Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler)

from ..config import get_settings
from ..const import ClipFormat, JobPhase, StorageMode, SubscriptionPlan
from ..logging import get_logger
from ..models import ClipOptions
from ..services.pipeline import pipeline
from ..services.progress import render_progress_message
from ..services.presets import PRESETS, get_default_preset
from ..services.preferences import get_preferences_store
from ..utils import URLValidationError, validate_source_url
from . import messages
from .keyboards import settings_keyboard, start_keyboard, status_keyboard

logger = get_logger(__name__)


def _get_user_plan(context: ContextTypes.DEFAULT_TYPE) -> SubscriptionPlan:
    plan = context.user_data.get("plan", SubscriptionPlan.FREE.value)
    try:
        return SubscriptionPlan(plan)
    except ValueError:
        return SubscriptionPlan.FREE


def _parse_options(args: list[str], base_options: ClipOptions) -> ClipOptions:
    options = base_options.model_copy(deep=True)
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "clips":
            options.clips = int(value)
        elif key in {"durée", "duree", "duration"}:
            options.duration = int(value)
        elif key == "format":
            options.format = ClipFormat(value)
        elif key == "subs":
            options.subs = value
        elif key == "lang":
            options.lang = value
        elif key == "style_subs":
            options.style_subs = value
        elif key == "watermark":
            options.watermark = value
        elif key == "watermark_text":
            options.watermark_text = value
        elif key == "music_ducking":
            options.music_ducking = value.lower() == "on"
        elif key in {"intro_outro_skip", "skip"}:
            options.intro_outro_skip = int(value)
        elif key == "ai_pick":
            options.ai_pick = value.lower() == "on"
        elif key == "diversité_clips" or key == "diversite_clips":
            options.diversite_clips = value.lower() == "on"
        elif key == "safe_faces_text":
            options.safe_faces_text = value.lower() == "on"
    return options


async def _ensure_storage_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> StorageMode:
    cached = context.user_data.get("storage_mode")
    if cached:
        try:
            return StorageMode(cached)
        except ValueError:
            pass
    store = get_preferences_store()
    default_mode = get_settings().storage_mode_enum
    prefs = await store.get(update.effective_user.id, default_mode)
    context.user_data["storage_mode"] = prefs.storage_mode.value
    return prefs.storage_mode


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pro_mode = context.user_data.get("pro_mode", False)
    storage_mode = await _ensure_storage_mode(update, context)
    await update.effective_chat.send_message(
        messages.start_header(storage_mode),
        reply_markup=start_keyboard(pro_mode, storage_mode),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(messages.HELP_MESSAGE, parse_mode=ParseMode.MARKDOWN)


async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(messages.plans_message(), parse_mode=ParseMode.MARKDOWN)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    snapshot = pipeline.get_status_snapshot()
    lines = ["📊 *Statut des jobs*"]
    if snapshot["active"]:
        lines.append("En cours :")
        lines.extend(f"• {item}" for item in snapshot["active"])
    if snapshot["queued"]:
        lines.append("En file :")
        lines.extend(f"• {item}" for item in snapshot["queued"])
    if len(lines) == 1:
        lines.append("Aucun job en cours.")
    await update.effective_chat.send_message("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def clip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_chat.send_message(messages.ERROR_INVALID_URL)
        return
    url = context.args[0]
    try:
        validate_source_url(url)
    except URLValidationError:
        await update.effective_chat.send_message(messages.ERROR_INVALID_URL)
        return
    base_preset = get_default_preset()
    options = _parse_options(context.args[1:], base_preset.options)
    plan = _get_user_plan(context)
    storage_mode = await _ensure_storage_mode(update, context)
    try:
        state = await pipeline.submit_job(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            bot=context.bot,
            source_url=url,
            options=options,
            plan=plan,
            mode="auto",
            storage_mode=storage_mode,
        )
    except ValueError as exc:
        await update.effective_chat.send_message(f"⚠️ {exc}")
        return
    progress = state.tracker.update_progress(phase=state.tracker.current_phase, ratio_in_phase=0.0)
    message = await update.effective_chat.send_message(
        messages.job_created(storage_mode),
        reply_markup=status_keyboard(state.request.job_id, False, plan is SubscriptionPlan.PRO),
    )
    state.status_message_id = message.message_id
    context.application.create_task(_poll_progress(update, context, state.request.job_id))


async def select_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_chat.send_message(messages.ERROR_INVALID_URL)
        return
    url = context.args[0]
    try:
        validate_source_url(url)
    except URLValidationError:
        await update.effective_chat.send_message(messages.ERROR_INVALID_URL)
        return
    plan = _get_user_plan(context)
    storage_mode = await _ensure_storage_mode(update, context)
    preset = next(p for p in PRESETS if "Manuel" in p.name)
    options = preset.options
    state = await pipeline.submit_job(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        bot=context.bot,
        source_url=url,
        options=options,
        plan=plan,
        mode="manual",
        storage_mode=storage_mode,
    )
    msg = (
        "🎛️ Mode manuel initialisé. Utilise les boutons pour définir les segments."
        " Ajoute jusqu'à 5 clips et confirme pour lancer le rendu."
    )
    await update.effective_chat.send_message(msg)
    state.status_message_id = None


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message("Quel job dois-je annuler ? Utilise le bouton ❌ du statut.")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage_mode = await _ensure_storage_mode(update, context)
    await update.effective_chat.send_message(
        messages.settings_overview(storage_mode),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=settings_keyboard(storage_mode),
    )


async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "toggle_pro":
        current = context.user_data.get("pro_mode", False)
        context.user_data["pro_mode"] = not current
        storage_mode = await _ensure_storage_mode(update, context)
        await query.edit_message_reply_markup(start_keyboard(not current, storage_mode))
        return
    if data.startswith("preset:"):
        preset_name = data.split(":", 1)[1]
        preset = next((p for p in PRESETS if p.name == preset_name), None)
        if not preset:
            await query.answer("Preset introuvable", show_alert=True)
            return
        context.user_data["selected_preset"] = preset.name
        await query.answer(f"Preset {preset.name} sélectionné.")
        return
    if data == "settings:open":
        storage_mode = await _ensure_storage_mode(update, context)
        await query.message.reply_text(
            messages.settings_overview(storage_mode),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=settings_keyboard(storage_mode),
        )
        return
    if data == "settings:close":
        try:
            await query.message.delete()
        except Exception:  # pragma: no cover - message déjà supprimé
            pass
        return
    if data.startswith("settings:storage:"):
        _, _, raw_mode = data.split(":", 2)
        try:
            storage_mode = StorageMode(raw_mode)
        except ValueError:
            await query.answer("Mode inconnu", show_alert=True)
            return
        context.user_data["storage_mode"] = storage_mode.value
        store = get_preferences_store()
        await store.set_storage_mode(update.effective_user.id, storage_mode)
        await query.edit_message_reply_markup(settings_keyboard(storage_mode))
        await query.answer(f"Stockage {storage_mode.value} activé.")
        return
    job_id, action = data.split(":", 1)
    state = pipeline.get_job_state(job_id)
    if not state:
        await query.answer("Job introuvable.", show_alert=True)
        return
    if action == "mute":
        state.muted = True
        await query.answer("Notifications réduites.")
    elif action == "details":
        state.details_mode = not state.details_mode
        await query.edit_message_reply_markup(
            status_keyboard(job_id, state.details_mode, state.request.plan is SubscriptionPlan.PRO)
        )
    elif action == "priority":
        if state.request.plan is SubscriptionPlan.PRO:
            await query.answer("Déjà en Pro.")
        else:
            await query.answer("Passe en Pro via /plans pour un traitement prioritaire !", show_alert=True)
    elif action == "cancel":
        await pipeline.cancel_job(job_id, reason="user_button")
        await query.edit_message_text(messages.CANCELLED_MESSAGE)


async def _poll_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, job_id: str) -> None:
    chat_id = update.effective_chat.id
    while True:
        await asyncio.sleep(3)
        state = pipeline.get_job_state(job_id)
        if not state:
            break
        if not state.status_message_id or state.muted:
            continue
        progress = state.last_progress
        if not progress:
            continue
        details = []
        if state.storage_allocation and state.storage_allocation.warnings:
            details.extend(f"⚠️ {warning}" for warning in state.storage_allocation.warnings)
        if state.details_mode and progress.details:
            details.extend(f"{k}: {v}" for k, v in progress.details.items())
        if not details:
            details = ["Traitement en cours…"]
        if state.tracker.stalled():
            details.append("Ralentissement détecté, recalcul de l'ETA…")
        text = render_progress_message(progress, details)
        if progress.phase is JobPhase.DELIVERY:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=state.status_message_id,
            text=text,
            reply_markup=status_keyboard(job_id, state.details_mode, state.request.plan is SubscriptionPlan.PRO),
        )


HANDLERS = [
    CommandHandler("start", start),
    CommandHandler("help", help_command),
    CommandHandler("plans", plans_command),
    CommandHandler("status", status_command),
    CommandHandler("clip", clip_command),
    CommandHandler("select", select_command),
    CommandHandler("cancel", cancel_command),
    CommandHandler("settings", settings_command),
    CallbackQueryHandler(callback_query),
]
