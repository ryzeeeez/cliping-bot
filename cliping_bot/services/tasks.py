"""Client HTTP pour orchestrer les workers cloud ou locaux."""

from __future__ import annotations

import asyncio

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - permet les tests sans dépendances réseau
    httpx = None

from ..config import get_settings
from ..logging import get_logger
from ..models import JobRequest, WorkerResult

logger = get_logger(__name__)


class TaskClient:
    def __init__(self) -> None:
        settings = get_settings()
        if httpx is None:
            raise RuntimeError("httpx n'est pas installé. Requis pour contacter les workers.")
        self._http = httpx.AsyncClient(base_url=str(settings.tasks_api_url), timeout=90)
        self._max_retries = 3

    async def __aenter__(self) -> "TaskClient":  # pragma: no cover
        return self

    async def __aexit__(self, *exc: object) -> None:  # pragma: no cover
        await self._http.aclose()

    async def submit_job(self, request: JobRequest) -> None:
        payload = request.model_dump(mode="json")
        logger.info(
            "worker.submit",
            job_id=request.job_id,
            mode=request.mode,
            storage_mode=request.storage_mode.value,
        )
        await self._request("POST", "/jobs", json=payload)

    async def cancel_job(self, job_id: str) -> None:
        logger.info("worker.cancel", job_id=job_id)
        await self._request("DELETE", f"/jobs/{job_id}")

    async def fetch_result(self, job_id: str) -> WorkerResult:
        response = await self._request("GET", f"/jobs/{job_id}")
        return WorkerResult.model_validate(response.json())

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        delay = 0.5
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    logger.error(
                        "worker.request_failed", method=method, url=url, error=str(exc), attempt=attempt
                    )
                    raise
                logger.warning(
                    "worker.retry", method=method, url=url, error=str(exc), attempt=attempt
                )
                await asyncio.sleep(delay)
                delay *= 2


async def with_task_client(func, *args, **kwargs):
    async with TaskClient() as client:
        return await func(client, *args, **kwargs)
