"""Orchestrateur des jobs et intégration worker/Telegram."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..const import JobPhase, StorageMode, SubscriptionPlan
from ..logging import get_logger
from ..models import ClipOptions, JobProgress, JobRequest, WorkerResult
from ..utils import validate_source_url
from .progress import ProgressTracker, render_progress_message
from .storage import StorageAllocation, get_storage_coordinator
from .tasks import TaskClient

logger = get_logger(__name__)


@dataclass
class JobState:
    request: JobRequest
    tracker: ProgressTracker
    status_message_id: Optional[int] = None
    muted: bool = False
    details_mode: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_progress: Optional[JobProgress] = None
    queue_position: int = 0
    storage_allocation: StorageAllocation | None = None


class JobPipeline:
    """Gestion centralisée des jobs utilisateurs."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._storage = get_storage_coordinator()

    async def submit_job(
        self,
        user_id: int,
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
        state = JobState(request=request, tracker=tracker, storage_allocation=allocation)
        async with self._lock:
            self._jobs[job_id] = state
            await self._queue.put(job_id)
            state.queue_position = self._queue.qsize() - 1
        asyncio.create_task(self._dispatch_job(state))
        return state

    async def _dispatch_job(self, state: JobState) -> None:
        async with TaskClient() as client:
            try:
                await client.submit_job(state.request)
                logger.info(
                    "pipeline.dispatched",
                    job_id=state.request.job_id,
                    storage_mode=state.request.storage_mode.value,
                    output_path=state.request.output_path,
                )
            except Exception as exc:  # pragma: no cover - log + cleanup
                logger.error("pipeline.dispatch_error", job_id=state.request.job_id, error=str(exc))
                await self.cancel_job(state.request.job_id, reason="dispatch_error")

    async def cancel_job(self, job_id: str, reason: str = "user_cancel") -> None:
        state = self._jobs.pop(job_id, None)
        if not state:
            return
        async with TaskClient() as client:
            try:
                await client.cancel_job(job_id)
            except Exception as exc:  # pragma: no cover
                logger.warning("pipeline.cancel_failed", job_id=job_id, error=str(exc))
        if state.storage_allocation:
            await self._storage.cleanup(state.storage_allocation, force=True)
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

    async def complete_job(self, job_id: str, result: WorkerResult) -> WorkerResult | None:
        state = self._jobs.pop(job_id, None)
        if not state:
            logger.warning("pipeline.complete_unknown", job_id=job_id)
            return None
        if state.storage_allocation:
            await self._storage.cleanup(state.storage_allocation)
        logger.info(
            "pipeline.completed",
            job_id=job_id,
            download_url=str(result.download_url),
            expires_at=result.expires_at.isoformat(),
            storage_mode=result.storage_mode.value,
            telegram_file_id=result.telegram_file_id,
        )
        return result

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


pipeline = JobPipeline()
