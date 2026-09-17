from functools import lru_cache
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import StorageProvider
from .local import LocalStorageProvider


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_BACKEND == "local":
        return LocalStorageProvider(settings.MEDIA_ROOT)
    raise ImproperlyConfigured(
        f"Proveedor de almacenamiento desconocido: {settings.STORAGE_BACKEND}"
    )


class StorageService:
    def __init__(self, provider: StorageProvider | None = None):
        self.provider = provider or get_storage_provider()

    @staticmethod
    def upload_part_key(upload_id, part_number: int) -> str:
        return str(
            PurePosixPath("temporary", str(upload_id), "parts", f"{part_number:08d}")
        )

    @staticmethod
    def video_key(operator_id, event_id, video_id) -> str:
        return str(
            PurePosixPath(
                "operators",
                str(operator_id),
                "events",
                str(event_id),
                "videos",
                f"{video_id}.mp4",
            )
        )

    def delete_many(self, keys) -> None:
        for key in keys:
            if key:
                self.provider.delete(key)

