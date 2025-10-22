"""Pipeline local pour le clipping automatique."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from ..const import ClipFormat, FORMAT_RESOLUTIONS, JobPhase
from ..logging import get_logger
from ..models import ClipOptions, ClipSlice, JobRequest

logger = get_logger(__name__)


TELEGRAM_FILE_LIMIT = 2 * 1024 * 1024 * 1024  # 2 GiB approx.
SILENCE_RE = re.compile(r"silence_(start|end):\s*([0-9.]+)")
CHAPTER_BLACKLIST = {"intro", "outro", "sponsor", "credit"}


class ClipProcessingError(Exception):
    """Erreur fonctionnelle pendant le traitement d'un clip."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


class SourceNotAccessibleError(ClipProcessingError):
    """La source est privée, DRM ou protégée."""


class FileTooLargeError(ClipProcessingError):
    """Fichier supérieur à la limite Telegram."""

    def __init__(self, path: Path) -> None:
        size_gb = path.stat().st_size / (1024 ** 3)
        super().__init__(
            "Clip trop volumineux pour Telegram",
            user_message=(
                "❌ Ce clip pèse {:.2f} Go, au-delà de la limite Telegram (≈2 Go).\n"
                "👉 Relance avec `format=youtube` ou `durée=30` pour réduire la taille."
            ).format(size_gb),
        )
        self.path = path


@dataclass
class AutoClipResult:
    clips: list[ClipSlice]
    files: list[Path]
    metadata: dict[str, Any]
    duration: float
    warnings: list[str]


class AutoClipRunner:
    """Réalise un job /clip en local (macOS)."""

    def __init__(self, request: JobRequest, options: ClipOptions, job_dir: Path) -> None:
        self.request = request
        self.options = options
        self.job_dir = job_dir
        self.metadata: dict[str, Any] = {}
        self.video_path: Path | None = None
        self.duration: float = 0.0

    async def run(self, progress_cb) -> AutoClipResult:
        await progress_cb(JobPhase.ANALYSE, 0.05, ["Analyse de la source…"])
        self.metadata = await self._fetch_metadata()
        self.duration = float(self.metadata.get("duration") or 0.0)
        title = self.metadata.get("title") or "Source"
        await progress_cb(JobPhase.ANALYSE, 1.0, [f"Analyse… {title[:60]}"])

        await progress_cb(JobPhase.AUTO_PICK, 0.05, ["Préparation du téléchargement…"])
        self.video_path = await self._download(progress_cb)
        if not self.duration:
            self.duration = await self._resolve_duration()
        await progress_cb(JobPhase.AUTO_PICK, 1.0, ["Téléchargement terminé."])

        await progress_cb(JobPhase.SUBTITLES, 0.1, ["Préparation des segments…"])
        clips = await self._select_segments()
        if not clips:
            raise ClipProcessingError("Aucun segment pertinent trouvé", "❌ Impossible d'extraire un clip pertinent.")
        await progress_cb(
            JobPhase.SUBTITLES,
            1.0,
            [f"{len(clips)} segment(s) sélectionné(s)."]
        )

        await progress_cb(JobPhase.EXPORT, 0.02, ["Encodage des clips…"])
        files = await self._encode_clips(clips, progress_cb)
        return AutoClipResult(clips=clips, files=files, metadata=self.metadata, duration=self.duration, warnings=[])

    async def _fetch_metadata(self) -> dict[str, Any]:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
            "--skip-download",
            self.request.source_url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            message = stderr.decode("utf-8", errors="ignore")
            if "This video is private" in message or "private" in message.lower():
                raise SourceNotAccessibleError(
                    "Source privée", "❌ La vidéo est privée/protégée, je ne peux pas clipper."
                )
            if "sign in" in message.lower() or "drm" in message.lower():
                raise SourceNotAccessibleError(
                    "Source protégée", "❌ Le flux est protégé par DRM ou nécessite une connexion."
                )
            raise ClipProcessingError(
                f"Échec métadonnées: {message.strip() or 'yt-dlp a échoué'}",
                "❌ Impossible de récupérer les métadonnées de la vidéo.",
            )
        try:
            return json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - rare
            raise ClipProcessingError("Métadonnées illisibles", "❌ Analyse impossible (métadonnées corrompues).") from exc

    async def _resolve_duration(self) -> float:
        if self.metadata.get("duration"):
            try:
                return float(self.metadata["duration"])
            except (TypeError, ValueError):
                pass
        if not self.video_path or not self.video_path.exists():
            return 0.0
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(self.video_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return 0.0
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return 0.0

    async def _download(self, progress_cb) -> Path:
        output_template = str(self.job_dir / "source.%(ext)s")
        cmd = [
            "yt-dlp",
            self.request.source_url,
            "-o",
            output_template,
            "--merge-output-format",
            "mp4",
            "--newline",
            "--progress-template",
            "download:%(progress._percent_str)s",
            "--print",
            "filename",
            "--no-warnings",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        download_path: Path | None = None
        if proc.stdout is None:
            raise ClipProcessingError("Flux yt-dlp inaccessible", "❌ Téléchargement impossible.")

        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("download:") and "%" in line:
                try:
                    percent_str = line.split(":", 1)[1].strip().rstrip("%")
                    percent = float(percent_str)
                except ValueError:
                    continue
                ratio = max(0.0, min(1.0, percent / 100.0))
                await progress_cb(
                    JobPhase.AUTO_PICK,
                    min(0.9, ratio * 0.9),
                    [f"Téléchargement… {percent:.1f}%"],
                )
            elif line.startswith("/") or line.startswith("."):
                candidate = Path(line).resolve()
                if candidate.exists():
                    download_path = candidate

        stderr = await proc.stderr.read() if proc.stderr else b""
        returncode = await proc.wait()
        if returncode != 0:
            message = stderr.decode("utf-8", errors="ignore")
            if "This video is private" in message or "private" in message.lower():
                raise SourceNotAccessibleError(
                    "Source privée", "❌ La vidéo est privée/protégée, je ne peux pas clipper."
                )
            raise ClipProcessingError(
                f"Téléchargement impossible: {message.strip() or 'yt-dlp a échoué'}",
                "❌ Échec du téléchargement via yt-dlp.",
            )

        if not download_path:
            mp4_files = sorted(self.job_dir.glob("source.*"))
            if mp4_files:
                download_path = mp4_files[0]
        if not download_path:
            raise ClipProcessingError("Fichier téléchargé introuvable", "❌ Téléchargement terminé mais le fichier est introuvable.")
        if download_path.suffix != ".mp4":
            target = download_path.with_suffix(".mp4")
            if download_path.exists():
                download_path.rename(target)
            download_path = target
        return download_path

    async def _select_segments(self) -> list[ClipSlice]:
        chapters = self.metadata.get("chapters") or []
        clips: list[ClipSlice] = []
        target = float(self.options.duration)
        intro_skip = float(self.options.intro_outro_skip)
        max_duration = self.duration or float(self.metadata.get("duration") or 0)

        if chapters:
            for chapter in chapters:
                title = (chapter.get("title") or "").lower()
                if any(bad in title for bad in CHAPTER_BLACKLIST):
                    continue
                start = float(chapter.get("start_time") or 0.0)
                end = float(chapter.get("end_time") or max_duration)
                if end <= start:
                    continue
                start = max(0.0, start + intro_skip)
                end = min(max_duration, end)
                if end - start < 5:
                    continue
                duration = min(target, end - start)
                clips.append(ClipSlice(start=start, end=start + duration))
                if len(clips) >= self.options.clips:
                    break
        if len(clips) >= self.options.clips:
            return clips[: self.options.clips]

        if self.video_path is None:
            return clips

        silences = await self._detect_silences()
        segments = self._build_non_silent_segments(silences, max_duration, intro_skip)
        min_spacing = 10.0
        for start, end in segments:
            if len(clips) >= self.options.clips:
                break
            span = end - start
            if span < 3:
                continue
            start_candidate = start
            if span > target:
                start_candidate = start + (span - target) / 2
            start_candidate = max(0.0, min(start_candidate, max_duration - target))
            end_candidate = min(max_duration, start_candidate + target)
            slice_candidate = ClipSlice(start=start_candidate, end=end_candidate)
            if any(abs(slice_candidate.start - existing.start) < min_spacing for existing in clips):
                continue
            clips.append(slice_candidate)

        clips = sorted(clips, key=lambda item: item.start)
        if len(clips) >= self.options.clips:
            return clips[: self.options.clips]

        # Fallback uniforme
        remaining = self.options.clips - len(clips)
        base_start = intro_skip
        usable = max(0.0, max_duration - 2 * intro_skip)
        if usable <= 0:
            usable = max_duration
        step = (usable - target) / max(remaining, 1) if usable > target else target + min_spacing
        current = base_start
        while len(clips) < self.options.clips and current < max_duration:
            end = min(max_duration, current + target)
            slice_candidate = ClipSlice(start=current, end=end)
            if any(abs(slice_candidate.start - existing.start) < min_spacing for existing in clips):
                current += max(5.0, step)
                continue
            clips.append(slice_candidate)
            current += max(5.0, step)

        return clips[: self.options.clips]

    async def _detect_silences(self) -> list[tuple[float, float]]:
        if not self.video_path:
            return []
        cmd = [
            "ffmpeg",
            "-i",
            str(self.video_path),
            "-af",
            "silencedetect=noise=-35dB:d=0.8",
            "-f",
            "null",
            "-",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return []
        silences: list[tuple[float, float]] = []
        current_start: float | None = None
        for line in stderr.decode("utf-8", errors="ignore").splitlines():
            match = SILENCE_RE.search(line)
            if not match:
                continue
            kind, value = match.groups()
            timestamp = float(value)
            if kind == "start":
                current_start = timestamp
            elif kind == "end" and current_start is not None:
                silences.append((current_start, timestamp))
                current_start = None
        return silences

    def _build_non_silent_segments(
        self, silences: list[tuple[float, float]], max_duration: float, intro_skip: float
    ) -> list[tuple[float, float]]:
        segments: list[tuple[float, float]] = []
        cursor = 0.0
        for start, end in silences:
            if start - cursor > 0.5:
                segments.append((max(cursor, intro_skip), start))
            cursor = max(cursor, end)
        if cursor < max_duration:
            segments.append((cursor, max_duration))
        cleaned = []
        for start, end in segments:
            start = max(0.0, start)
            end = min(max_duration, end)
            if end - start < 2:
                continue
            cleaned.append((start, end))
        return cleaned

    async def _encode_clips(self, clips: Iterable[ClipSlice], progress_cb) -> list[Path]:
        if not self.video_path:
            raise ClipProcessingError("Fichier source introuvable", "❌ Vidéo source introuvable pour l'encodage.")
        clip_list = list(clips)
        result_files: list[Path] = []
        width, height = await self._probe_resolution()
        target_width, target_height = FORMAT_RESOLUTIONS[self.options.format]
        fallback = {
            ClipFormat.TIKTOK: (720, 1280),
            ClipFormat.SQUARE: (720, 720),
            ClipFormat.YOUTUBE: (1280, 720),
        }[self.options.format]
        if max(width, height) < max(target_width, target_height):
            target_width, target_height = fallback

        filter_chain = self._build_filter_chain(target_width, target_height)

        total = len(clip_list) or 1
        for index, clip in enumerate(clip_list, start=1):
            safe_margin = 0.3
            start = max(0.0, clip.start - safe_margin)
            end = min(self.duration or clip.end + safe_margin, clip.end + safe_margin)
            duration = max(0.5, end - start)
            output_path = self.job_dir / f"clip_{index:02d}.mp4"
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(self.video_path),
                "-t",
                f"{duration:.3f}",
                "-vf",
                filter_chain,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-af",
                "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise ClipProcessingError(
                    f"Échec FFmpeg: {stderr.decode('utf-8', errors='ignore').strip()}",
                    "❌ FFmpeg n'a pas pu encoder le clip.",
                )
            if output_path.stat().st_size > TELEGRAM_FILE_LIMIT:
                raise FileTooLargeError(output_path)
            result_files.append(output_path)
            await progress_cb(
                JobPhase.EXPORT,
                min(1.0, index / total),
                [f"Encodage clip {index}/{total}…"],
            )
        return result_files

    async def _probe_resolution(self) -> tuple[int, int]:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(self.video_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return (1920, 1080)
        line = stdout.decode().strip()
        try:
            width_str, height_str = line.split("x")
            return int(width_str), int(height_str)
        except ValueError:
            return (1920, 1080)

    def _build_filter_chain(self, width: int, height: int) -> str:
        if self.options.format is ClipFormat.YOUTUBE:
            return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        # TikTok & square: crop pour remplir
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"

