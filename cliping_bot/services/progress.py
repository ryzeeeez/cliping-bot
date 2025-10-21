"""Gestion du calcul de progression et des messages associés."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable

from ..const import JobPhase, PHASE_WEIGHTS, PROGRESS_STALL_WARNING_SECONDS
from ..models import JobProgress
from ..utils import human_readable_timedelta


@dataclass
class PhaseStats:
    history: list[float] = field(default_factory=list)

    def record(self, duration: float) -> None:
        self.history.append(duration)
        if len(self.history) > 50:
            self.history.pop(0)

    def avg(self) -> float:
        if not self.history:
            return 1.0
        return sum(self.history) / len(self.history)


class ProgressTracker:
    """Suit l'avancement d'un job et calcule le pourcentage/ETA."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.phase_started_at: dict[JobPhase, float] = {}
        self.phase_stats: dict[JobPhase, PhaseStats] = {phase: PhaseStats() for phase in JobPhase}
        self.current_phase: JobPhase = JobPhase.ANALYSE
        self.percent = 0.0
        self._last_update_ts: float = time.time()
        self._last_edit_ts: float = 0.0

    def phase_started(self, phase: JobPhase) -> None:
        self.current_phase = phase
        self.phase_started_at[phase] = time.time()

    def phase_completed(self, phase: JobPhase) -> None:
        start = self.phase_started_at.get(phase)
        if start:
            duration = time.time() - start
            self.phase_stats[phase].record(duration)
        end_percent = PHASE_WEIGHTS[phase][1]
        self.percent = float(end_percent)
        self._last_update_ts = time.time()

    def update_progress(self, phase: JobPhase, ratio_in_phase: float) -> JobProgress:
        start_percent, end_percent = PHASE_WEIGHTS[phase]
        percent = start_percent + (end_percent - start_percent) * max(0.0, min(1.0, ratio_in_phase))
        self.percent = percent
        self.current_phase = phase
        eta = self._estimate_eta(phase, ratio_in_phase)
        self._last_update_ts = time.time()
        return JobProgress(
            job_id=self.job_id,
            phase=phase,
            percent=round(percent, 1),
            eta_seconds=eta,
            message_ts=datetime.utcnow(),
            details={},
        )

    def should_edit_message(self) -> bool:
        return (time.time() - self._last_edit_ts) >= 2.0

    def mark_message_edited(self) -> None:
        self._last_edit_ts = time.time()

    def stalled(self) -> bool:
        return (time.time() - self._last_update_ts) > PROGRESS_STALL_WARNING_SECONDS

    def _estimate_eta(self, phase: JobPhase, ratio_in_phase: float) -> float | None:
        remaining = 0.0
        for phase_iter in JobPhase:
            start, end = PHASE_WEIGHTS[phase_iter]
            span = (end - start) / 100
            if phase_iter == phase:
                span *= max(0.0, 1.0 - ratio_in_phase)
            elif PHASE_WEIGHTS[phase_iter][0] <= PHASE_WEIGHTS[phase][1]:
                if phase_iter.value <= phase.value:
                    continue
            remaining += self.phase_stats[phase_iter].avg() * span
        return max(1.0, remaining) if remaining else None


def render_progress_message(progress: JobProgress, status_lines: Iterable[str]) -> str:
    """Construit le message utilisateur (français) avec barre et ETA."""

    filled = int(progress.percent // 5)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    eta = human_readable_timedelta(progress.eta_seconds) if progress.eta_seconds else "calcul..."
    lines = [
        f"{progress.phase.name.title().replace('_', ' ')} — {progress.percent:.1f}%",
        f"ETA {eta}",
        f"[{bar}]",
        *status_lines,
    ]
    return "\n".join(lines)
