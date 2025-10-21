"""Sélection automatique des meilleurs moments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models import ClipOptions, ClipSlice


@dataclass
class ScoredWindow:
    start: float
    end: float
    score: float


class AutoClipper:
    """Algorithme heuristique pour prioriser les meilleurs segments."""

    def __init__(self, options: ClipOptions) -> None:
        self.options = options

    def pick(self, candidates: Iterable[ScoredWindow]) -> list[ClipSlice]:
        sorted_candidates = sorted(candidates, key=lambda w: w.score, reverse=True)
        selected: list[ClipSlice] = []
        for window in sorted_candidates:
            if len(selected) >= self.options.clips:
                break
            if any(abs(window.start - existing.start) < 10 for existing in selected):
                continue
            duration = window.end - window.start
            target = self.options.duration
            if duration > target * 1.2:
                window_end = window.start + target * 1.2
            elif duration < target * 0.6:
                window_end = window.start + target * 0.6
            else:
                window_end = window.end
            selected.append(ClipSlice(start=window.start, end=window_end))
        return selected
