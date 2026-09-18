import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.events.models import ReservedVideoToken

from .models import Video
from .processing import process_video_file

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.videos.tasks.prepare_public_video",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def prepare_public_video(self, video_id: str) -> str:
    with transaction.atomic():
        video = Video.objects.select_for_update().get(pk=video_id)
        if video.status == Video.Status.READY:
            return video.status
        if video.status not in {Video.Status.UPLOADED, Video.Status.PROCESSING, Video.Status.FAILED}:
            return video.status
        video.status = Video.Status.PROCESSING
        video.save(update_fields=("status", "updated_at"))

    try:
        processed = process_video_file(video)
    except Exception:
        Video.objects.filter(pk=video_id).update(status=Video.Status.FAILED)
        logger.exception("video_processing_failed", extra={"metadata": {"video_id": video_id}})
        raise

    with transaction.atomic():
        video = Video.objects.select_for_update().select_related("token_reservation").get(pk=video_id)
        video.duration_ms = processed.duration_ms
        video.thumbnail_storage_key = processed.thumbnail_storage_key
        video.status = Video.Status.READY
        video.save(update_fields=("duration_ms", "thumbnail_storage_key", "status", "updated_at"))
        reservation = video.token_reservation
        reservation.status = ReservedVideoToken.Status.READY
        reservation.save(update_fields=("status",))
    logger.info("video_ready", extra={"metadata": {"video_id": video_id}})
    return video.status


@shared_task(name="apps.videos.tasks.enqueue_unprocessed_videos")
def enqueue_unprocessed_videos(batch_size: int = 100) -> int:
    stale = timezone.now() - timedelta(minutes=20)
    video_ids = list(
        Video.objects.filter(
            Q(status=Video.Status.UPLOADED)
            | Q(status=Video.Status.PROCESSING, updated_at__lte=stale)
        )
        .order_by("updated_at")
        .values_list("id", flat=True)[:batch_size]
    )
    for video_id in video_ids:
        prepare_public_video.delay(str(video_id))
    return len(video_ids)
