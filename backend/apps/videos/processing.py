import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.storage.service import StorageService

from .models import Video


class VideoProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessedVideo:
    duration_ms: int
    thumbnail_storage_key: str


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10 * 60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VideoProcessingError("No fue posible analizar el video.") from exc


def _probe(path: Path) -> int:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        payload = json.loads(result.stdout)
        if not payload.get("streams"):
            raise ValueError
        duration = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoProcessingError("El archivo no contiene un video reproducible.") from exc
    if duration <= 0:
        raise VideoProcessingError("La duración del video no es válida.")
    return round(duration * 1000)


def process_video_file(video: Video, storage: StorageService | None = None) -> ProcessedVideo:
    storage = storage or StorageService()
    if not video.storage_key or not storage.provider.exists(video.storage_key):
        raise VideoProcessingError("El archivo del video no existe.")

    with TemporaryDirectory(prefix="cabina360-video-") as directory:
        source_path = Path(directory) / "source.mp4"
        thumbnail_path = Path(directory) / "thumbnail.jpg"
        with storage.provider.open(video.storage_key) as source, source_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)

        duration_ms = _probe(source_path)
        capture_second = min(1.0, max(0.0, duration_ms / 2000))
        _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                f"{capture_second:.3f}",
                "-i",
                str(source_path),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(720,iw)':-2",
                "-q:v",
                "3",
                str(thumbnail_path),
            ]
        )
        if not thumbnail_path.is_file() or thumbnail_path.stat().st_size == 0:
            raise VideoProcessingError("No fue posible generar la miniatura.")

        key = storage.thumbnail_key(video.operator_id, video.event_id, video.id)
        with thumbnail_path.open("rb") as thumbnail:
            storage.provider.put_stream(
                key,
                thumbnail,
                expected_size=thumbnail_path.stat().st_size,
            )
    return ProcessedVideo(duration_ms=duration_ms, thumbnail_storage_key=key)
