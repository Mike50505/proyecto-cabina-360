import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.videos.models import Video

from .models import UploadSession
from .services import _delete_part_files

logger = logging.getLogger(__name__)


@shared_task(name="apps.uploads.tasks.cleanup_expired_upload_sessions")
def cleanup_expired_upload_sessions(batch_size: int = 100) -> int:
    session_ids = list(
        UploadSession.objects.filter(
            status__in=UploadSession.ACTIVE_STATUSES,
            expires_at__lte=timezone.now(),
        )
        .order_by("expires_at")
        .values_list("id", flat=True)[:batch_size]
    )
    cleaned = 0
    for session_id in session_ids:
        with transaction.atomic():
            session = (
                UploadSession.objects.select_for_update()
                .select_related("video")
                .filter(pk=session_id, status__in=UploadSession.ACTIVE_STATUSES)
                .first()
            )
            if session is None or session.expires_at > timezone.now():
                continue
            part_keys = list(session.parts.values_list("storage_key", flat=True))
            session.status = UploadSession.Status.EXPIRED
            session.error_code = "UPLOAD_EXPIRED"
            session.video.status = Video.Status.FAILED
            session.save(update_fields=("status", "error_code", "updated_at"))
            session.video.save(update_fields=("status", "updated_at"))
            transaction.on_commit(lambda keys=part_keys: _delete_part_files(keys))
            cleaned += 1
    if cleaned:
        logger.info("expired_uploads_cleaned", extra={"metadata": {"count": cleaned}})
    return cleaned

