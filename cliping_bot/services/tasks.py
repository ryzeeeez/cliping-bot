"""Client HTTP pour orchestrer les workers cloud."""

from __future__ import annotations

import httpx

from ..config import get_settings
from ..logging import get_logger
from ..models import JobRequest, WorkerResult

logger = get_logger(__name__)


class TaskClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._http = httpx.AsyncClient(base_url=str(settings.tasks_api_url), timeout=60)

    async def __aenter__(self) -> "TaskClient":  # pragma: no cover
        return self

    async def __aexit__(self, *exc: object) -> None:  # pragma: no cover
        await self._http.aclose()

    async def submit_job(self, request: JobRequest) -> None:
        payload = request.model_dump(mode="json")
        logger.info("worker.submit", job_id=request.job_id, mode=request.mode)
        response = await self._http.post("/jobs", json=payload)
        response.raise_for_status()

    async def cancel_job(self, job_id: str) -> None:
        logger.info("worker.cancel", job_id=job_id)
        response = await self._http.delete(f"/jobs/{job_id}")
        response.raise_for_status()

    async def fetch_result(self, job_id: str) -> WorkerResult:
        response = await self._http.get(f"/jobs/{job_id}")
        response.raise_for_status()
        return WorkerResult.model_validate(response.json())


async def with_task_client(func, *args, **kwargs):
    async with TaskClient() as client:
        return await func(client, *args, **kwargs)
