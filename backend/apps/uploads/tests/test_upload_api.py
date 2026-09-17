import hashlib
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.tests.factories import create_operator_account
from apps.events.models import Event, EventType, ReservedVideoToken
from apps.storage.service import StorageService, get_storage_provider
from apps.uploads.models import UploadSession
from apps.uploads.tasks import cleanup_expired_upload_sessions
from apps.videos.models import Video


class UploadApiTests(APITestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=Path(self.temporary.name),
            UPLOAD_PART_SIZE_BYTES=4,
            MAX_UPLOAD_SIZE_BYTES=1024,
        )
        self.settings_override.enable()
        get_storage_provider.cache_clear()
        self.user, self.operator, self.plan, _ = create_operator_account("upload")
        self.event_type = EventType.objects.get(code="wedding")
        self.event = Event.objects.create(
            operator=self.operator,
            event_type=self.event_type,
            name="Evento upload",
            event_date=timezone.now(),
            status=Event.Status.ACTIVE,
            settings={},
        )
        self.reservation = ReservedVideoToken.objects.create(event=self.event)
        self.video_uuid = uuid.uuid4()
        self.content = b"\x00\x00\x00\x18ftypmp42abcdefgh"
        self.client.force_authenticate(self.user)

    def tearDown(self):
        get_storage_provider.cache_clear()
        self.settings_override.disable()
        self.temporary.cleanup()

    def payload(self, **overrides):
        payload = {
            "video_uuid": str(self.video_uuid),
            "event_uuid": str(self.event.id),
            "public_video_token": self.reservation.public_token,
            "original_filename": "camera/final.mp4",
            "size_bytes": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
            "mime_type": "video/mp4",
            "duration_ms": 8000,
        }
        payload.update(overrides)
        return payload

    def create_session(self, key="device:video:1", **overrides):
        return self.client.post(
            "/api/v1/uploads/",
            self.payload(**overrides),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def put_part(self, upload_id, number, content):
        return self.client.put(
            f"/api/v1/uploads/{upload_id}/parts/{number}/",
            data=content,
            content_type="application/octet-stream",
            HTTP_X_PART_SHA256=hashlib.sha256(content).hexdigest(),
        )

    def test_complete_resumable_upload_publishes_verified_video(self):
        created = self.create_session()
        upload_id = created.data["id"]

        parts = [self.content[index : index + 4] for index in range(0, len(self.content), 4)]
        for number, content in enumerate(parts):
            response = self.put_part(upload_id, number, content)
            self.assertEqual(response.status_code, 201)

        completed = self.client.post(f"/api/v1/uploads/{upload_id}/complete/")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["status"], UploadSession.Status.COMPLETED)
        video = Video.objects.get(pk=self.video_uuid)
        self.assertEqual(video.status, Video.Status.UPLOADED)
        self.assertEqual(video.checksum_sha256, hashlib.sha256(self.content).hexdigest())
        provider = get_storage_provider()
        self.assertTrue(provider.exists(video.storage_key))
        with provider.open(video.storage_key) as stream:
            self.assertEqual(stream.read(), self.content)

    def test_create_is_idempotent_and_rejects_changed_payload(self):
        first = self.create_session()
        repeated = self.create_session()
        changed = self.create_session(size_bytes=9)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.data["id"], first.data["id"])
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(UploadSession.objects.count(), 1)

    def test_second_key_cannot_create_parallel_session_for_video(self):
        first = self.create_session()

        second = self.create_session(key="another-key")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["error"]["code"], "UPLOAD_ALREADY_ACTIVE")

    def test_missing_parts_prevent_completion(self):
        upload_id = self.create_session().data["id"]
        self.put_part(upload_id, 0, b"abcd")

        response = self.client.post(f"/api/v1/uploads/{upload_id}/complete/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "UPLOAD_PARTS_MISSING")

    def test_wrong_final_checksum_is_rejected_without_final_file(self):
        created = self.create_session(sha256="0" * 64)
        upload_id = created.data["id"]
        parts = [self.content[index : index + 4] for index in range(0, len(self.content), 4)]
        for number, content in enumerate(parts):
            self.put_part(upload_id, number, content)

        response = self.client.post(f"/api/v1/uploads/{upload_id}/complete/")

        self.assertEqual(response.status_code, 422)
        key = StorageService.video_key(self.operator.id, self.event.id, self.video_uuid)
        self.assertFalse(get_storage_provider().exists(key))

    def test_non_mp4_content_is_rejected_after_checksum_verification(self):
        self.content = b"this-is-not-an-mp4"
        created = self.create_session()
        upload_id = created.data["id"]
        parts = [self.content[index : index + 4] for index in range(0, len(self.content), 4)]
        for number, content in enumerate(parts):
            self.put_part(upload_id, number, content)

        response = self.client.post(f"/api/v1/uploads/{upload_id}/complete/")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"]["code"], "INVALID_VIDEO_CONTENT")

    def test_other_operator_cannot_read_upload(self):
        upload_id = self.create_session().data["id"]
        other_user, _, _, _ = create_operator_account("upload-other")
        self.client.force_authenticate(other_user)

        response = self.client.get(f"/api/v1/uploads/{upload_id}/")

        self.assertEqual(response.status_code, 404)

    def test_abort_allows_new_session_for_same_video(self):
        first = self.create_session()
        self.put_part(first.data["id"], 0, b"abcd")
        aborted = self.client.post(f"/api/v1/uploads/{first.data['id']}/abort/")

        retry = self.create_session(key="device:video:retry")

        self.assertEqual(aborted.status_code, 200)
        self.assertEqual(aborted.data["status"], UploadSession.Status.ABORTED)
        self.assertEqual(retry.status_code, 201)
        self.assertNotEqual(retry.data["id"], first.data["id"])

    def test_storage_quota_is_enforced(self):
        self.plan.max_storage_bytes = 5
        self.plan.save(update_fields=("max_storage_bytes",))

        response = self.create_session()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "STORAGE_QUOTA_EXCEEDED")

    def test_expired_session_cleanup_removes_temporary_parts(self):
        created = self.create_session()
        upload_id = created.data["id"]
        self.put_part(upload_id, 0, self.content[:4])
        session = UploadSession.objects.get(pk=upload_id)
        part_key = session.parts.get().storage_key
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=("expires_at",))

        with self.captureOnCommitCallbacks(execute=True):
            cleaned = cleanup_expired_upload_sessions()

        session.refresh_from_db()
        session.video.refresh_from_db()
        self.assertEqual(cleaned, 1)
        self.assertEqual(session.status, UploadSession.Status.EXPIRED)
        self.assertEqual(session.video.status, Video.Status.FAILED)
        self.assertFalse(get_storage_provider().exists(part_key))
