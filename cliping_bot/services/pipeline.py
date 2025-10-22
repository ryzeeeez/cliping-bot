"""Orchestrateur local du pipeline de clipping."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Bot
from telegram.constants import ChatAction

from ..const import JobPhase, StorageMode, SubscriptionPlan
from ..logging import get_logger
from ..models import ClipOptions, JobProgress, JobRequest
from ..utils import validate_source_url
from .local_clip import AutoClipResult, AutoClipRunner, ClipProcessingError
from .progress import ProgressTracker, render_progress_message
from .storage import StorageAllocation, get_storage_coordinator

logger = get_logger(__name__)


@dataclass
class JobState:
    request: JobRequest
    tracker: ProgressTracker
    bot: Bot
    chat_id: int
    status_message_id: Optional[int] = None
    muted: bool = False
    details_mode: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_progress: Optional[JobProgress] = None
    queue_position: int = 0
    storage_allocation: StorageAllocation | None = None


class JobPipeline:
    """Gestion centralisée des jobs /clip."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = asyncio.Lock()
        self._storage = get_storage_coordinator()
        self._upload_rates: list[float] = []

    async def submit_job(
        self,
        user_id: int,
        chat_id: int,
        bot: Bot,
        source_url: str,
        options: ClipOptions,
        plan: SubscriptionPlan,
        mode: str = "auto",
        manual_clips: Optional[list] = None,
        storage_mode: StorageMode | str | None = None,
    ) -> JobState:
        validate_source_url(source_url)
        options.ensure_plan_limits(plan)
        job_id = str(uuid.uuid4())
        requested_mode = storage_mode or self._storage.settings.storage_mode_enum
        if isinstance(requested_mode, str):
            try:
                storage_mode_enum = StorageMode(requested_mode)
            except ValueError:
                storage_mode_enum = self._storage.settings.storage_mode_enum
        else:
            storage_mode_enum = requested_mode
        allocation = await self._storage.allocate(job_id, storage_mode_enum)
        request = JobRequest(
            user_id=user_id,
            chat_id=chat_id,
            source_url=source_url,
            options=options,
            plan=plan,
            job_id=job_id,
            mode=mode,
            manual_clips=manual_clips,
            storage_mode=storage_mode_enum,
            output_path=str(allocation.base_path) if allocation.base_path else None,
            storage_metadata=allocation.metadata,
        )
        tracker = ProgressTracker(job_id)
        state = JobState(
            request=request,
            tracker=tracker,
            bot=bot,
            chat_id=chat_id,
            storage_allocation=allocation,
        )
        async with self._lock:
            self._jobs[job_id] = state
        asyncio.create_task(self._run_job(state))
        return state

    async def cancel_job(self, job_id: str, reason: str = "user_cancel") -> None:
        state = self._jobs.pop(job_id, None)
        if not state:
            return
        if state.storage_allocation:
            await self._storage.cleanup(state.storage_allocation, force=True)
        await state.bot.send_message(state.chat_id, "❌ Traitement annulé.")
        logger.info("pipeline.cancelled", job_id=job_id, reason=reason)

    async def register_progress(
        self,
        job_id: str,
        phase: JobPhase,
        ratio_in_phase: float,
        status_lines: list[str] | None = None,
    ) -> JobProgress | None:
        state = self._jobs.get(job_id)
        if not state:
            logger.warning("pipeline.progress_unknown", job_id=job_id)
            return None
        progress = state.tracker.update_progress(phase, ratio_in_phase)
        state.last_progress = progress
        storage_label = "Local" if state.request.storage_mode is StorageMode.LOCAL else "Cloud"
        progress.details["Stockage"] = storage_label
        if state.storage_allocation and state.storage_allocation.base_path:
            progress.details["Dossier"] = str(state.storage_allocation.base_path)
        if state.storage_allocation and state.storage_allocation.warnings:
            progress.details["Avertissements"] = " · ".join(state.storage_allocation.warnings)
        if state.storage_allocation and state.storage_allocation.metadata:
            for key, value in state.storage_allocation.metadata.items():
                progress.details[f"meta:{key}"] = str(value)
        if status_lines is None:
            status_lines = ["Traitement en cours…"]
        message = render_progress_message(progress, status_lines)
        logger.info("pipeline.progress", job_id=job_id, message=message)
        return progress

    def get_status_snapshot(self) -> dict[str, list[str]]:
        active = []
        queued = []
        for job in self._jobs.values():
            label = f"Job {job.request.job_id[:8]} — {job.request.mode}"
            if job.tracker.percent >= 100:
                continue
            if job.tracker.current_phase == JobPhase.ANALYSE:
                queued.append(label)
            else:
                active.append(
                    f"{label} · {job.tracker.current_phase.name} · {job.tracker.percent:.1f}%"
                )
        return {"active": active, "queued": queued}

    def get_job_state(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    async def _run_job(self, state: JobState) -> None:
        job_id = state.request.job_id
        logger.info("pipeline.start", job_id=job_id, storage_mode=state.request.storage_mode.value)
        try:
            allocation = state.storage_allocation
            if state.request.storage_mode is not StorageMode.LOCAL:
                raise ClipProcessingError(
                    "Mode cloud non disponible",
                    "❌ Le mode cloud n'est pas disponible en exécution locale.",
                )
            if not allocation or not allocation.base_path:
                raise ClipProcessingError(
                    "Aucun dossier pour le job",
                    "❌ Impossible de préparer le dossier temporaire.",
                )
            progress_cb = self._make_progress_callback(state)
            runner = AutoClipRunner(state.request, state.request.options, allocation.base_path)
            result = await runner.run(progress_cb)
            await self._deliver(state, result)
            await self._finalize_success(state, result)
        except ClipProcessingError as exc:
            await self._handle_failure(state, exc.user_message)
        except Exception as exc:  # pragma: no cover - garde-fou
            logger.exception("pipeline.job_failed", job_id=job_id, error=str(exc))
            await self._handle_failure(
                state,
                "❌ Une erreur interne est survenue pendant le clipping. Réessaie dans quelques minutes.",
            )

    def _make_progress_callback(self, state: JobState):
        async def _callback(phase: JobPhase, ratio: float, lines: list[str]) -> None:
            if state.tracker.current_phase is not phase:
                state.tracker.phase_started(phase)
            await self.register_progress(state.request.job_id, phase, ratio, lines)
            if ratio >= 0.999:
                state.tracker.phase_completed(phase)

        return _callback

    async def _deliver(self, state: JobState, result: AutoClipResult) -> None:
        files = result.files
        if not files:
            raise ClipProcessingError("Aucun clip encodé", "❌ Aucun clip n'a pu être encodé.")
        job_id = state.request.job_id
        state.tracker.phase_started(JobPhase.DELIVERY)
        total = len(files)
        for index, path in enumerate(files, start=1):
            await self._upload_clip(state, path, index, total)
        await self.register_progress(job_id, JobPhase.DELIVERY, min(0.995, 1 - 1e-6), ["Finalisation…"])

    async def _upload_clip(self, state: JobState, path: Path, index: int, total: int) -> None:
        job_id = state.request.job_id
        file_size = path.stat().st_size
        base_ratio = (index - 1) / max(total, 1)
        estimated_duration = file_size / max(self._average_upload_rate(), 1_000_000)
        start = time.monotonic()
        progress_task = asyncio.create_task(
            self._delivery_progress_loop(state, base_ratio, total, index, estimated_duration)
        )
        action_task = asyncio.create_task(self._chat_action_loop(state))
        try:
            with path.open("rb") as stream:
                await state.bot.send_video(
                    chat_id=state.chat_id,
                    video=stream,
                    supports_streaming=True,
                    caption=f"Clip {index}/{total}",
                )
        finally:
            progress_task.cancel()
            action_task.cancel()
            with contextlib.suppress(Exception):
                await progress_task
            with contextlib.suppress(Exception):
                await action_task
        elapsed = max(time.monotonic() - start, 0.1)
        rate = file_size / elapsed
        self._upload_rates.append(rate)
        if len(self._upload_rates) > 20:
            self._upload_rates.pop(0)
        await self.register_progress(
            job_id,
            JobPhase.DELIVERY,
            base_ratio + (1 / max(total, 1)) * 0.95,
            [f"Clip {index}/{total} envoyé ({file_size / 1_000_000:.1f} Mo)."],
        )

    async def _delivery_progress_loop(
        self,
        state: JobState,
        base_ratio: float,
        total: int,
        index: int,
        estimated_duration: float,
    ) -> None:
        job_id = state.request.job_id
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            ratio = min(1.0, elapsed / max(estimated_duration, 0.5))
            phase_ratio = min(0.99, base_ratio + ratio / max(total, 1))
            await self.register_progress(
                job_id,
                JobPhase.DELIVERY,
                phase_ratio,
                [f"Envoi à Telegram… clip {index}/{total} · {ratio * 100:.0f}%"],
            )
            await asyncio.sleep(1)

    async def _chat_action_loop(self, state: JobState) -> None:
        while True:
            await state.bot.send_chat_action(chat_id=state.chat_id, action=ChatAction.UPLOAD_VIDEO)
            await asyncio.sleep(4)

    async def _finalize_success(self, state: JobState, result: AutoClipResult) -> None:
        await self.register_progress(state.request.job_id, JobPhase.DELIVERY, 1.0, ["Terminé ✅ 100%"])
        await state.bot.send_message(
            state.chat_id,
            "Terminé ✅ Les clips ont été envoyés sur ce chat.",
        )
        self._schedule_cleanup(state, force=False)

    async def _handle_failure(self, state: JobState, message: str) -> None:
        job_id = state.request.job_id
        await state.bot.send_message(state.chat_id, message)
        await self.register_progress(job_id, state.tracker.current_phase, state.tracker.percent / 100, [message])
        self._schedule_cleanup(state, force=True)

    def _schedule_cleanup(self, state: JobState, force: bool) -> None:
        asyncio.create_task(self._cleanup_later(state, force))

    async def _cleanup_later(self, state: JobState, force: bool) -> None:
        await asyncio.sleep(3)
        await self._cleanup(state, force)

    async def _cleanup(self, state: JobState, force: bool) -> None:
        job_id = state.request.job_id
        if state.storage_allocation:
            await self._storage.cleanup(state.storage_allocation, force=force)
        self._jobs.pop(job_id, None)
        logger.info("pipeline.cleanup", job_id=job_id)

    def _average_upload_rate(self) -> float:
        if not self._upload_rates:
            return 4_000_000.0  # ~4 MB/s par défaut
        return sum(self._upload_rates) / len(self._upload_rates)


pipeline = JobPipeline()

