import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType, ReservedVideoToken
from apps.storage.service import StorageService, get_storage_provider

from ..models import Video


class VideoApiTests(APITestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=Path(self.temporary.name))
        self.settings_override.enable()
        get_storage_provider.cache_clear()
        self.user, self.operator, _, _ = create_operator_account("video")
        event_type = EventType.objects.get(code="party")
        self.event = Event.objects.create(
            operator=self.operator,
            event_type=event_type,
            name="Evento video",
            event_date=timezone.now(),
            status=Event.Status.ACTIVE,
            settings={},
        )
        reservation = ReservedVideoToken.objects.create(
            event=self.event,
            status=ReservedVideoToken.Status.ASSIGNED,
        )
        content = b"verified-video"
        video_id = uuid.uuid4()
        key = StorageService.video_key(self.operator.id, self.event.id, video_id)
        stored = get_storage_provider().put_stream(
            key, BytesIO(content), expected_size=len(content)
        )
        self.video = Video.objects.create(
            id=video_id,
            operator=self.operator,
            event=self.event,
            token_reservation=reservation,
            original_filename="video.mp4",
            storage_key=key,
            expected_size_bytes=len(content),
            size_bytes=len(content),
            mime_type="video/mp4",
            expected_sha256=stored.sha256,
            checksum_sha256=stored.sha256,
            status=Video.Status.UPLOADED,
            uploaded_at=timezone.now(),
        )
        reservation.assigned_video_uuid = video_id
        reservation.save(update_fields=("assigned_video_uuid",))
        self.client.force_authenticate(self.user)

    def tearDown(self):
        get_storage_provider.cache_clear()
        self.settings_override.disable()
        self.temporary.cleanup()

    def test_delete_removes_physical_file_and_expires_token(self):
        key = self.video.storage_key

        response = self.client.delete(f"/api/v1/videos/{self.video.id}/")

        self.assertEqual(response.status_code, 204)
        self.video.refresh_from_db()
        self.video.token_reservation.refresh_from_db()
        self.assertEqual(self.video.status, Video.Status.DELETED)
        self.assertEqual(
            self.video.token_reservation.status, ReservedVideoToken.Status.EXPIRED
        )
        self.assertFalse(get_storage_provider().exists(key))

    def test_other_operator_cannot_access_video_or_event_list(self):
        other_user, _, _, _ = create_operator_account("video-other")
        self.client.force_authenticate(other_user)

        detail = self.client.get(f"/api/v1/videos/{self.video.id}/")
        event_list = self.client.get(f"/api/v1/events/{self.event.id}/videos/")

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(event_list.status_code, 404)

