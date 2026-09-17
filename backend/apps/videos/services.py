import logging

from django.db import transaction

from apps.events.models import ReservedVideoToken
from apps.storage.service import StorageService

from .models import Video

logger = logging.getLogger(__name__)


def delete_video(video: Video) -> Video:
    with transaction.atomic():
        locked = Video.objects.select_for_update().select_related("token_reservation").get(
            pk=video.pk
        )
        if locked.status == Video.Status.DELETED:
            return locked
        locked.status = Video.Status.PENDING_DELETE
        locked.save(update_fields=("status", "updated_at"))

    storage = StorageService()
    keys = [locked.storage_key, locked.thumbnail_storage_key]
    keys.extend(
        locked.upload_sessions.values_list("parts__storage_key", flat=True)
    )
    storage.delete_many(keys)

    with transaction.atomic():
        locked = Video.objects.select_for_update().select_related("token_reservation").get(
            pk=video.pk
        )
        locked.status = Video.Status.DELETED
        locked.save(update_fields=("status", "updated_at"))
        reservation = locked.token_reservation
        reservation.status = ReservedVideoToken.Status.EXPIRED
        reservation.save(update_fields=("status",))
    logger.info("video_deleted", extra={"metadata": {"video_id": str(video.pk)}})
    return locked
