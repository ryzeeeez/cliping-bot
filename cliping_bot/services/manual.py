"""Gestion du mode manuel assisté."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import ClipSlice, ManualSelectionState


@dataclass
class ManualActionResult:
    state: ManualSelectionState
    message: str
    preview_url: Optional[str] = None


class ManualSession:
    def __init__(self, state: ManualSelectionState) -> None:
        self.state = state

    def shift(self, seconds: float) -> ManualActionResult:
        duration = self.state.duration
        if self.state.current_start is None:
            self.state.current_start = max(0.0, min(duration, seconds))
        else:
            self.state.current_start = max(0.0, min(duration, self.state.current_start + seconds))
        return ManualActionResult(self.state, self._status_message("Position ajustée."))

    def mark_start(self) -> ManualActionResult:
        self.state.current_start = self.state.current_start or 0.0
        return ManualActionResult(self.state, self._status_message("Début fixé."))

    def mark_end(self) -> ManualActionResult:
        if self.state.current_start is None:
            return ManualActionResult(self.state, "Fixe d'abord un début." )
        end = max(self.state.current_start + 0.3, self.state.current_end or self.state.current_start)
        end = min(end, self.state.duration)
        self.state.current_end = end
        return ManualActionResult(self.state, self._status_message("Fin fixée."))

    def add_clip(self) -> ManualActionResult:
        if self.state.current_start is None or self.state.current_end is None:
            return ManualActionResult(self.state, "Fixe un début et une fin avant d'ajouter le clip.")
        if len(self.state.clips) >= 5:
            return ManualActionResult(self.state, "Tu as atteint la limite de 5 clips.")
        slice_ = ClipSlice(start=self.state.current_start, end=self.state.current_end + 0.3)
        self.state.clips.append(slice_)
        self.state.current_start = None
        self.state.current_end = None
        return ManualActionResult(self.state, self._status_message("Clip ajouté."))

    def summary(self) -> str:
        if not self.state.clips:
            return "Aucun clip sélectionné pour l'instant."
        rows = [
            f"Clip {idx+1}: {clip.start:.1f}s → {clip.end:.1f}s ({clip.duration:.1f}s)"
            for idx, clip in enumerate(self.state.clips)
        ]
        return "\n".join(rows)

    def _status_message(self, prefix: str) -> str:
        return f"{prefix}\n{self.summary()}"
