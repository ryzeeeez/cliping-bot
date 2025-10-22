"""Modèles Pydantic décrivant les presets et options pro."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, PositiveInt, conint, constr

from .const import (
    DEFAULT_CLIP_COUNT,
    DEFAULT_CLIP_DURATION,
    DEFAULT_INTRO_OUTRO_SKIP,
    ClipFormat,
    JobPhase,
    StorageMode,
    SubscriptionPlan,
)


class ClipSlice(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class ClipOptions(BaseModel):
    clips: Annotated[int, conint(ge=1, le=10)] = DEFAULT_CLIP_COUNT
    duration: Annotated[int, conint(ge=5, le=120)] = DEFAULT_CLIP_DURATION
    format: ClipFormat = ClipFormat.TIKTOK
    subs: Literal["auto", "on", "off"] = "auto"
    lang: str = "auto"
    style_subs: Literal["clean", "karaoke", "compact"] = "clean"
    watermark: Literal["on", "off"] = "on"
    watermark_text: Optional[constr(strip_whitespace=True, max_length=32)] = None
    music_ducking: bool = False
    intro_outro_skip: Annotated[int, conint(ge=0, le=30)] = DEFAULT_INTRO_OUTRO_SKIP
    ai_pick: bool = True
    diversite_clips: bool = True
    safe_faces_text: bool = True
    max_duree_source: Optional[int] = Field(None, ge=600)

    def ensure_plan_limits(self, plan: SubscriptionPlan) -> None:
        if plan is SubscriptionPlan.FREE:
            if self.duration > 60:
                raise ValueError("Durée maximum 60 s en plan Free.")
            if self.clips > 3:
                raise ValueError("Maximum 3 clips en plan Free.")
            self.watermark = "on"
            if not self.watermark_text:
                self.watermark_text = "@clipingbot"
        else:
            if not self.watermark_text:
                self.watermark_text = "@clipingbot"


class Preset(BaseModel):
    name: str
    description: str
    options: ClipOptions
    emoji: str


class ManualSelectionState(BaseModel):
    source_url: HttpUrl
    duration: float
    clips: list[ClipSlice] = Field(default_factory=list)
    current_start: Optional[float] = None
    current_end: Optional[float] = None
    last_preview_url: Optional[HttpUrl] = None


class JobProgress(BaseModel):
    job_id: str
    phase: JobPhase
    percent: float = Field(..., ge=0, le=100)
    eta_seconds: Optional[float] = Field(None, ge=0)
    message_ts: datetime
    details: dict[str, str] = Field(default_factory=dict)


class JobRequest(BaseModel):
    user_id: int
    chat_id: int
    source_url: HttpUrl
    options: ClipOptions
    plan: SubscriptionPlan
    job_id: str
    mode: Literal["auto", "manual", "podcast"] = "auto"
    manual_clips: Optional[list[ClipSlice]] = None
    storage_mode: StorageMode = StorageMode.LOCAL
    output_path: Optional[str] = None
    storage_metadata: dict[str, str] = Field(default_factory=dict)


class WorkerResult(BaseModel):
    job_id: str
    download_url: HttpUrl
    expires_at: datetime
    telegram_file_id: Optional[str] = None
    clips: list[ClipSlice]
    metadata: dict[str, str] = Field(default_factory=dict)
    storage_mode: StorageMode = StorageMode.CLOUD
    local_paths: list[str] = Field(default_factory=list)
