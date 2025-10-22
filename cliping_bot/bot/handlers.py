"""Handlers Telegram basés sur aiogram."""

from __future__ import annotations

import asyncio
import contextlib

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import get_settings
from ..const import ClipFormat, JobPhase, StorageMode, SubscriptionPlan
from ..logging import get_logger
from ..models import ClipOptions
from ..services.pipeline import pipeline
from ..services.preferences import get_preferences_store
from ..services.presets import PRESETS, get_default_preset
from ..services.progress import render_progress_message
from ..utils import URLValidationError, validate_source_url
from . import messages
from .keyboards import settings_keyboard, start_keyboard, status_keyboard

logger = get_logger(__name__)
router = Router()


async def _get_user_plan(_: Message) -> SubscriptionPlan:
    # Plans avancés gérés ailleurs ; par défaut Free
    return SubscriptionPlan.FREE


async def _ensure_storage_mode(message: Message, state: FSMContext) -> StorageMode:
    data = await state.get_data()
    raw_mode = data.get("storage_mode")
    if raw_mode:
        try:
            return StorageMode(raw_mode)
        except ValueError:
            pass
    store = get_preferences_store()
    default_mode = get_settings().storage_mode_enum
    prefs = await store.get(message.from_user.id, default_mode)
    await state.update_data(storage_mode=prefs.storage_mode.value)
    return prefs.storage_mode


async def _toggle_pro_mode(state: FSMContext) -> bool:
    data = await state.get_data()
    current = bool(data.get("pro_mode"))
    await state.update_data(pro_mode=not current)
    return not current


def _parse_options(parts: list[str], base_options: ClipOptions) -> ClipOptions:
    options = base_options.model_copy(deep=True)
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        try:
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
        except ValueError:
            continue
    return options


async def _start_progress_task(job_id: str) -> None:
    while True:
        await asyncio.sleep(2.5)
        state = pipeline.get_job_state(job_id)
        if not state:
            return
        if not state.status_message_id or state.muted:
            continue
        progress = state.last_progress
        if not progress or not state.tracker.should_edit_message():
            continue
        lines = list(state.last_status_lines or ["Traitement en cours…"])
        if state.details_mode and progress.details:
            lines.extend(f"{k}: {v}" for k, v in progress.details.items())
        if state.tracker.stalled():
            lines.append("Ralentissement détecté, recalcul en cours…")
        text = render_progress_message(progress, lines)
        if progress.phase is JobPhase.DELIVERY:
            await state.bot.send_chat_action(chat_id=state.chat_id, action=ChatAction.UPLOAD_VIDEO)
        try:
            await state.bot.edit_message_text(
                chat_id=state.chat_id,
                message_id=state.status_message_id,
                text=text,
                reply_markup=status_keyboard(
                    state.request.job_id,
                    state.details_mode,
                    state.request.plan is SubscriptionPlan.PRO,
                ),
            )
            state.tracker.mark_message_edited()
        except TelegramBadRequest as exc:  # pragma: no cover - ignore si message supprimé
            logger.warning("progress.edit_failed", error=str(exc))
            continue


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    storage_mode = await _ensure_storage_mode(message, state)
    data = await state.get_data()
    pro_mode = bool(data.get("pro_mode"))
    await message.answer(
        messages.start_header(storage_mode),
        reply_markup=start_keyboard(pro_mode, storage_mode),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(messages.HELP_MESSAGE)


@router.message(Command("plans"))
async def plans_command(message: Message) -> None:
    await message.answer(messages.plans_message())


@router.message(Command("status"))
async def status_command(message: Message) -> None:
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
    await message.answer("\n".join(lines))


@router.message(Command("settings"))
async def settings_command(message: Message, state: FSMContext) -> None:
    storage_mode = await _ensure_storage_mode(message, state)
    await message.answer(
        messages.settings_overview(storage_mode),
        reply_markup=settings_keyboard(storage_mode),
    )


@router.message(Command("clip"))
async def clip_command(message: Message, command: CommandObject, state: FSMContext) -> None:
    if not command.args:
        await message.answer(messages.ERROR_INVALID_URL)
        return
    parts = command.args.split()
    url = parts[0]
    try:
        validate_source_url(url)
    except URLValidationError:
        await message.answer(messages.ERROR_INVALID_URL)
        return
    base_preset = get_default_preset()
    options = _parse_options(parts[1:], base_preset.options)
    plan = await _get_user_plan(message)
    storage_mode = await _ensure_storage_mode(message, state)
    try:
        job_state = await pipeline.submit_job(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            bot=message.bot,
            source_url=url,
            options=options,
            plan=plan,
            mode="auto",
            storage_mode=storage_mode,
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    job_state.status_message_id = (
        await message.answer(
            messages.job_created(storage_mode),
            reply_markup=status_keyboard(job_state.request.job_id, False, plan is SubscriptionPlan.PRO),
        )
    ).message_id
    if not job_state.progress_task or job_state.progress_task.done():
        job_state.progress_task = asyncio.create_task(_start_progress_task(job_state.request.job_id))


@router.message(Command("select"))
async def select_command(message: Message, command: CommandObject, state: FSMContext) -> None:
    if not command.args:
        await message.answer(messages.ERROR_INVALID_URL)
        return
    url = command.args.split()[0]
    try:
        validate_source_url(url)
    except URLValidationError:
        await message.answer(messages.ERROR_INVALID_URL)
        return
    await state.update_data(manual_source=url)
    await message.answer(
        "🎛️ Mode manuel initialisé. Utilise les boutons pour définir les segments."
        " Ajoute jusqu'à 5 clips puis confirme pour lancer le rendu."
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    cancelled = await pipeline.cancel_job_for_user(message.from_user.id, reason="command_cancel")
    if cancelled:
        await message.answer("❌ Job annulé et nettoyé.")
    else:
        await message.answer("Aucun job en cours à annuler.")


@router.callback_query(F.data.startswith("preset:"))
async def preset_selected(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    preset_name = query.data.split(":", 1)[1]
    preset = next((p for p in PRESETS if p.name == preset_name), None)
    if not preset:
        await query.answer("Preset introuvable", show_alert=True)
        return
    await state.update_data(selected_preset=preset.name)
    await query.answer(f"Preset {preset.name} sélectionné.")


@router.callback_query(F.data == "toggle_pro")
async def toggle_pro(query: CallbackQuery, state: FSMContext) -> None:
    enabled = await _toggle_pro_mode(state)
    storage_mode = await _ensure_storage_mode(query.message, state)
    await query.message.edit_reply_markup(start_keyboard(enabled, storage_mode))
    await query.answer()


@router.callback_query(F.data == "settings:open")
async def open_settings(query: CallbackQuery, state: FSMContext) -> None:
    storage_mode = await _ensure_storage_mode(query.message, state)
    await query.message.answer(
        messages.settings_overview(storage_mode),
        reply_markup=settings_keyboard(storage_mode),
    )
    await query.answer()


@router.callback_query(F.data == "settings:close")
async def close_settings(query: CallbackQuery) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await query.message.delete()
    await query.answer()


@router.callback_query(F.data.startswith("settings:storage:"))
async def change_storage(query: CallbackQuery, state: FSMContext) -> None:
    raw_mode = query.data.split(":", 2)[2]
    try:
        storage_mode = StorageMode(raw_mode)
    except ValueError:
        await query.answer("Mode inconnu", show_alert=True)
        return
    store = get_preferences_store()
    await store.set_storage_mode(query.from_user.id, storage_mode)
    await state.update_data(storage_mode=storage_mode.value)
    await query.message.edit_reply_markup(settings_keyboard(storage_mode))
    await query.answer(f"Stockage {storage_mode.value} activé.")


@router.callback_query(F.data.contains(":"))
async def job_actions(query: CallbackQuery) -> None:
    data = query.data or ""
    if data.startswith("settings:") or data.startswith("preset:"):
        return
    job_id, action = data.split(":", 1)
    state = pipeline.get_job_state(job_id)
    if not state:
        await query.answer("Job introuvable", show_alert=True)
        return
    if action == "mute":
        state.muted = True
        await query.answer("Notifications réduites.")
    elif action == "details":
        state.details_mode = not state.details_mode
        await query.message.edit_reply_markup(
            status_keyboard(job_id, state.details_mode, state.request.plan is SubscriptionPlan.PRO)
        )
        await query.answer()
    elif action == "priority":
        if state.request.plan is SubscriptionPlan.PRO:
            await query.answer("Déjà en plan Pro.")
        else:
            await query.answer("Passe en Pro via /plans pour une priorité file !", show_alert=True)
    elif action == "cancel":
        await pipeline.cancel_job(job_id, reason="callback_cancel")
        await query.message.edit_text(messages.CANCELLED_MESSAGE)
        await query.answer()

