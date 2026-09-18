import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType, ReservedVideoToken

from ..models import Video
from ..processing import ProcessedVideo
from ..tasks import enqueue_unprocessed_videos, prepare_public_video


class VideoProcessingTaskTests(TestCase):
    def setUp(self):
        _, operator, _, _ = create_operator_account("processing")
        event = Event.objects.create(
            operator=operator,
            event_type=EventType.objects.get(code="party"),
            name="Evento procesamiento",
            event_date=timezone.now(),
            status=Event.Status.ACTIVE,
            settings={},
        )
        reservation = ReservedVideoToken.objects.create(
            event=event,
            status=ReservedVideoToken.Status.ASSIGNED,
        )
        self.video = Video.objects.create(
            id=uuid.uuid4(),
            operator=operator,
            event=event,
            token_reservation=reservation,
            original_filename="video.mp4",
            storage_key="video.mp4",
            expected_size_bytes=10,
            size_bytes=10,
            mime_type="video/mp4",
            expected_sha256="a" * 64,
            checksum_sha256="a" * 64,
            status=Video.Status.UPLOADED,
        )

    @patch("apps.videos.tasks.process_video_file")
    def test_task_publishes_video_and_token_idempotently(self, process):
        process.return_value = ProcessedVideo(8123, "thumbnails/video.jpg")

        first = prepare_public_video.run(str(self.video.id))
        second = prepare_public_video.run(str(self.video.id))

        self.video.refresh_from_db()
        self.video.token_reservation.refresh_from_db()
        self.assertEqual(first, Video.Status.READY)
        self.assertEqual(second, Video.Status.READY)
        self.assertEqual(self.video.status, Video.Status.READY)
        self.assertEqual(self.video.duration_ms, 8123)
        self.assertEqual(self.video.token_reservation.status, ReservedVideoToken.Status.READY)
        process.assert_called_once()

    @patch("apps.videos.tasks.prepare_public_video.delay")
    def test_recovery_enqueues_uploaded_video(self, delay):
        count = enqueue_unprocessed_videos()

        self.assertEqual(count, 1)
        delay.assert_called_once_with(str(self.video.id))
