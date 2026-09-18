from datetime import timedelta

import hashlib
import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType, ReservedVideoToken
from apps.storage.service import StorageService, get_storage_provider
from apps.videos.models import PublicVideoAccess, Video


class PublicGalleryTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=Path(self.temporary.name))
        self.settings_override.enable()
        get_storage_provider.cache_clear()
        _, operator, _, _ = create_operator_account("public")
        event_type = EventType.objects.get(code="party")
        self.event = Event.objects.create(
            operator=operator,
            event_type=event_type,
            name="Fiesta pública",
            event_date=timezone.now(),
            status=Event.Status.ACTIVE,
            settings={},
        )
        self.token = ReservedVideoToken.objects.create(event=self.event)

    def tearDown(self):
        get_storage_provider.cache_clear()
        self.settings_override.disable()
        self.temporary.cleanup()

    def make_ready_video(self):
        content = b"0123456789-video-content"
        video_id = uuid.uuid4()
        video_key = StorageService.video_key(self.event.operator_id, self.event.id, video_id)
        thumbnail_key = StorageService.thumbnail_key(self.event.operator_id, self.event.id, video_id)
        provider = get_storage_provider()
        stored = provider.put_stream(video_key, BytesIO(content), expected_size=len(content))
        provider.put_stream(thumbnail_key, BytesIO(b"jpeg"), expected_size=4)
        self.token.status = ReservedVideoToken.Status.READY
        self.token.assigned_video_uuid = video_id
        self.token.save(update_fields=("status", "assigned_video_uuid"))
        return Video.objects.create(
            id=video_id,
            operator=self.event.operator,
            event=self.event,
            token_reservation=self.token,
            original_filename="mi-video.mp4",
            storage_key=video_key,
            thumbnail_storage_key=thumbnail_key,
            expected_size_bytes=len(content),
            size_bytes=len(content),
            mime_type="video/mp4",
            expected_sha256=stored.sha256,
            checksum_sha256=stored.sha256,
            status=Video.Status.READY,
        ), content

    def test_event_page_is_available_without_account(self):
        response = self.client.get(f"/e/{self.event.public_token}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fiesta pública")

    def test_reserved_video_token_shows_pending_page(self):
        response = self.client.get(f"/v/{self.token.public_token}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu video se está preparando")

    def test_disabled_or_expired_event_returns_gone(self):
        self.event.retention_until = timezone.now() - timedelta(seconds=1)
        self.event.save(update_fields=("retention_until",))

        event_response = self.client.get(f"/e/{self.event.public_token}/")
        video_response = self.client.get(f"/v/{self.token.public_token}/")

        self.assertEqual(event_response.status_code, 410)
        self.assertEqual(video_response.status_code, 410)

    def test_unknown_token_does_not_reveal_an_event(self):
        response = self.client.get("/e/not-a-real-token/")

        self.assertEqual(response.status_code, 404)

        for endpoint in ("stream", "download", "thumbnail"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/v/not-a-real-token/{endpoint}/")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("X-Accel-Redirect", response)

    def test_ready_video_appears_in_gallery_and_detail(self):
        video, _ = self.make_ready_video()

        gallery = self.client.get(f"/e/{self.event.public_token}/")
        detail = self.client.get(f"/v/{self.token.public_token}/")

        self.assertContains(gallery, f"/v/{self.token.public_token}/")
        self.assertContains(detail, "Tu video está listo")
        self.assertContains(detail, f"/v/{self.token.public_token}/stream/")
        self.assertEqual(video.public_accesses.filter(action=PublicVideoAccess.Action.VIEW).count(), 1)

    def test_stream_supports_ranges_and_rejects_invalid_ranges(self):
        video, content = self.make_ready_video()
        url = f"/v/{self.token.public_token}/stream/"

        response = self.client.get(url, HTTP_RANGE="bytes=3-8")
        invalid = self.client.get(url, HTTP_RANGE="bytes=999-1000")

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes 3-8/{len(content)}")
        self.assertEqual(b"".join(response.streaming_content), content[3:9])
        self.assertEqual(invalid.status_code, 416)
        self.assertEqual(video.public_accesses.filter(action=PublicVideoAccess.Action.STREAM).count(), 1)

    def test_download_is_streamed_with_safe_disposition(self):
        _, content = self.make_ready_video()

        response = self.client.get(f"/v/{self.token.public_token}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), content)

    @override_settings(CADDY_ACCEL_REDIRECT_ENABLED=True)
    def test_caddy_accel_redirects_only_after_public_authorization(self):
        video, _ = self.make_ready_video()

        stream = self.client.get(f"/v/{self.token.public_token}/stream/")
        download = self.client.get(f"/v/{self.token.public_token}/download/")
        thumbnail = self.client.get(f"/v/{self.token.public_token}/thumbnail/")

        self.assertEqual(stream.status_code, 200)
        self.assertEqual(stream["X-Accel-Redirect"], f"/{video.storage_key}")
        self.assertNotIn(video.storage_key, stream.content.decode())
        self.assertEqual(download["X-Accel-Redirect"], f"/{video.storage_key}")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(
            thumbnail["X-Accel-Redirect"], f"/{video.thumbnail_storage_key}"
        )

        self.event.retention_until = timezone.now() - timedelta(seconds=1)
        self.event.save(update_fields=("retention_until",))

        expired_stream = self.client.get(f"/v/{self.token.public_token}/stream/")
        expired_download = self.client.get(f"/v/{self.token.public_token}/download/")
        expired_thumbnail = self.client.get(f"/v/{self.token.public_token}/thumbnail/")

        self.assertEqual(expired_stream.status_code, 404)
        self.assertEqual(expired_download.status_code, 404)
        self.assertEqual(expired_thumbnail.status_code, 404)
        self.assertNotIn("X-Accel-Redirect", expired_stream)
