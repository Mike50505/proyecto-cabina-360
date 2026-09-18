import logging
import math
from datetime import timedelta
from pathlib import PurePath

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.core.exceptions import Conflict, UnprocessableEntity
from apps.events.models import Event, ReservedVideoToken
from apps.operators.models import Operator
from apps.storage.exceptions import StorageValidationError
from apps.storage.service import StorageService
from apps.subscriptions.services import current_subscription
from apps.videos.models import Video

from .models import UploadPart, UploadSession

logger = logging.getLogger(__name__)


def _safe_filename(value: str) -> str:
    filename = PurePath(value.replace("\\", "/")).name.strip()
    return filename[:255] or "video.mp4"


@transaction.atomic
def create_upload_session(*, operator: Operator, data: dict, idempotency_key: str):
    operator = Operator.objects.select_for_update().get(pk=operator.pk)
    existing = UploadSession.objects.select_related("video").filter(
        operator=operator, idempotency_key=idempotency_key
    ).first()
    if existing:
        compatible = (
            existing.video_id == data["video_uuid"]
            and existing.video.event_id == data["event_uuid"]
            and existing.video.public_token == data["public_video_token"]
            and existing.expected_size_bytes == data["size_bytes"]
            and existing.expected_sha256 == data["sha256"]
            and existing.video.mime_type == data["mime_type"]
            and existing.video.duration_ms == data.get("duration_ms")
            and existing.video.original_filename == _safe_filename(data["original_filename"])
        )
        if not compatible:
            raise Conflict(
                "La clave de idempotencia ya se usó con otros datos.",
                code="idempotency_conflict",
            )
        return existing, False

    subscription = current_subscription(operator)
    if subscription is None:
        raise ValidationError(
            {"subscription": "No existe una política de almacenamiento."},
            code="subscription_missing",
        )

    event = Event.objects.filter(pk=data["event_uuid"], operator=operator).first()
    if event is None:
        raise NotFound("El evento no existe.", code="event_not_found")
    if event.status in {
        Event.Status.EXPIRED,
        Event.Status.PENDING_DELETE,
        Event.Status.DELETED,
    }:
        raise Conflict("El evento ya no acepta videos.", code="event_unavailable")

    token = ReservedVideoToken.objects.select_for_update().filter(
        public_token=data["public_video_token"], event=event
    ).first()
    if token is None:
        raise ValidationError(
            {"public_video_token": "El token no pertenece al evento."},
            code="invalid_video_token",
        )
    if token.assigned_video_uuid and token.assigned_video_uuid != data["video_uuid"]:
        raise Conflict("El token ya está asignado.", code="video_token_assigned")

    video = Video.objects.select_for_update().filter(pk=data["video_uuid"]).first()
    if video and video.operator_id != operator.id:
        raise Conflict("El identificador del video no está disponible.", code="video_conflict")
    if video and (
        video.event_id != event.id
        or video.expected_size_bytes != data["size_bytes"]
        or video.expected_sha256 != data["sha256"]
        or video.token_reservation_id != token.id
    ):
        raise Conflict("El video ya existe con otros datos.", code="video_conflict")
    if video and video.status in {Video.Status.UPLOADED, Video.Status.PROCESSING, Video.Status.READY}:
        raise Conflict("El video ya fue subido.", code="video_already_uploaded")

    if video:
        active_session = video.upload_sessions.filter(
            status__in=UploadSession.ACTIVE_STATUSES
        ).first()
        if active_session and active_session.expires_at <= timezone.now():
            active_session.status = UploadSession.Status.EXPIRED
            active_session.save(update_fields=("status", "updated_at"))
            active_session = None
        if active_session:
            raise Conflict(
                "El video ya tiene una sesión activa.", code="upload_already_active"
            )

    if video is None:
        used_bytes = (
            operator.videos.exclude(status=Video.Status.DELETED).aggregate(
                total=Sum("expected_size_bytes")
            )["total"]
            or 0
        )
        if used_bytes + data["size_bytes"] > subscription.plan.max_storage_bytes:
            raise ValidationError(
                {"size_bytes": "La subida excede el almacenamiento del plan."},
                code="storage_quota_exceeded",
            )
        video = Video.objects.create(
            id=data["video_uuid"],
            operator=operator,
            event=event,
            token_reservation=token,
            original_filename=_safe_filename(data["original_filename"]),
            expected_size_bytes=data["size_bytes"],
            mime_type=data["mime_type"],
            duration_ms=data.get("duration_ms"),
            expected_sha256=data["sha256"],
            expires_at=event.retention_until,
        )
        token.assigned_video_uuid = video.id
        token.status = ReservedVideoToken.Status.ASSIGNED
        token.assigned_at = timezone.now()
        token.save(update_fields=("assigned_video_uuid", "status", "assigned_at"))

    session = UploadSession.objects.create(
        operator=operator,
        video=video,
        idempotency_key=idempotency_key,
        expected_size_bytes=data["size_bytes"],
        expected_sha256=data["sha256"],
        part_size_bytes=min(settings.UPLOAD_PART_SIZE_BYTES, data["size_bytes"]),
        expires_at=timezone.now() + timedelta(hours=settings.UPLOAD_SESSION_HOURS),
    )
    return session, True


def expected_part_size(session: UploadSession, number: int) -> tuple[int, int]:
    total_parts = math.ceil(session.expected_size_bytes / session.part_size_bytes)
    if number < 0 or number >= total_parts:
        raise ValidationError(
            {"number": "El número de parte está fuera del rango esperado."},
            code="invalid_part_number",
        )
    offset = number * session.part_size_bytes
    size = min(session.part_size_bytes, session.expected_size_bytes - offset)
    return offset, size


def store_upload_part(
    *, session: UploadSession, number: int, stream, claimed_sha256: str = ""
) -> tuple[UploadPart, bool]:
    storage = StorageService()
    with transaction.atomic():
        session = UploadSession.objects.select_for_update().select_related("video").get(
            pk=session.pk
        )
        if session.status not in UploadSession.ACTIVE_STATUSES:
            raise Conflict("La sesión ya no acepta partes.", code="upload_not_receiving")
        if session.expires_at <= timezone.now():
            session.status = UploadSession.Status.EXPIRED
            session.save(update_fields=("status", "updated_at"))
            raise Conflict("La sesión expiró.", code="upload_expired")
        offset, expected_size = expected_part_size(session, number)
        existing = session.parts.filter(number=number).first()
        if existing and storage.provider.exists(existing.storage_key):
            if not claimed_sha256 or existing.sha256 == claimed_sha256.lower():
                return existing, False
            raise Conflict(
                "La parte ya existe con otro checksum.", code="upload_part_conflict"
            )
        if existing:
            existing.delete()

        key = storage.upload_part_key(session.id, number)
        try:
            stored = storage.provider.put_stream(key, stream, expected_size=expected_size)
        except StorageValidationError as exc:
            raise UnprocessableEntity(str(exc), code="invalid_part_size") from exc
        if claimed_sha256 and stored.sha256 != claimed_sha256.lower():
            storage.provider.delete(key)
            raise UnprocessableEntity(
                "El checksum de la parte no coincide.", code="part_checksum_mismatch"
            )
        part = UploadPart.objects.create(
            session=session,
            number=number,
            offset=offset,
            size_bytes=stored.size,
            sha256=stored.sha256,
            storage_key=stored.key,
        )
        session.received_bytes = session.parts.aggregate(total=Sum("size_bytes"))["total"] or 0
        session.status = UploadSession.Status.RECEIVING
        session.video.status = Video.Status.UPLOADING
        session.save(update_fields=("received_bytes", "status", "updated_at"))
        session.video.save(update_fields=("status", "updated_at"))
        return part, True


def _delete_part_files(keys):
    try:
        StorageService().delete_many(keys)
    except Exception:
        logger.exception("upload_part_cleanup_failed")


@transaction.atomic
def complete_upload_session(session: UploadSession) -> UploadSession:
    session = UploadSession.objects.select_for_update().select_related(
        "video", "video__event", "video__token_reservation"
    ).get(pk=session.pk)
    if session.status == UploadSession.Status.COMPLETED:
        return session
    if session.status not in UploadSession.ACTIVE_STATUSES:
        raise Conflict("La sesión no puede completarse.", code="upload_not_completable")

    parts = list(session.parts.order_by("number"))
    expected_count = math.ceil(session.expected_size_bytes / session.part_size_bytes)
    if [part.number for part in parts] != list(range(expected_count)):
        raise Conflict("Faltan partes de la subida.", code="upload_parts_missing")
    if sum(part.size_bytes for part in parts) != session.expected_size_bytes:
        raise Conflict("El tamaño recibido está incompleto.", code="upload_size_incomplete")

    session.status = UploadSession.Status.VERIFYING
    session.video.status = Video.Status.VERIFYING
    session.save(update_fields=("status", "updated_at"))
    session.video.save(update_fields=("status", "updated_at"))

    storage = StorageService()
    destination_key = storage.video_key(
        session.operator_id, session.video.event_id, session.video_id
    )
    try:
        stored = storage.provider.compose(
            [part.storage_key for part in parts],
            destination_key,
            expected_size=session.expected_size_bytes,
            expected_sha256=session.expected_sha256,
        )
    except StorageValidationError as exc:
        session.status = UploadSession.Status.FAILED
        session.error_code = "FINAL_CHECKSUM_MISMATCH"
        session.video.status = Video.Status.CORRUPT
        session.save(update_fields=("status", "error_code", "updated_at"))
        session.video.save(update_fields=("status", "updated_at"))
        raise UnprocessableEntity(str(exc), code="final_checksum_mismatch") from exc

    with storage.provider.open(stored.key) as uploaded_file:
        signature = uploaded_file.read(12)
    if len(signature) < 12 or signature[4:8] != b"ftyp":
        storage.provider.delete(stored.key)
        raise UnprocessableEntity(
            "El contenido no corresponde a un MP4 válido.", code="invalid_video_content"
        )

    now = timezone.now()
    session.status = UploadSession.Status.COMPLETED
    session.completed_at = now
    session.error_code = ""
    session.video.storage_backend = settings.STORAGE_BACKEND
    session.video.storage_key = stored.key
    session.video.size_bytes = stored.size
    session.video.checksum_sha256 = stored.sha256
    session.video.status = Video.Status.UPLOADED
    session.video.uploaded_at = now
    session.save(update_fields=("status", "completed_at", "error_code", "updated_at"))
    session.video.save(
        update_fields=(
            "storage_backend",
            "storage_key",
            "size_bytes",
            "checksum_sha256",
            "status",
            "uploaded_at",
            "updated_at",
        )
    )
    part_keys = [part.storage_key for part in parts]
    transaction.on_commit(lambda: _delete_part_files(part_keys))
    from apps.videos.tasks import prepare_public_video

    transaction.on_commit(
        lambda: prepare_public_video.delay(str(session.video_id)),
        robust=True,
    )
    logger.info(
        "video_uploaded",
        extra={"metadata": {"video_id": str(session.video_id), "size": stored.size}},
    )
    return session


@transaction.atomic
def abort_upload_session(session: UploadSession) -> UploadSession:
    session = UploadSession.objects.select_for_update().select_related("video").get(
        pk=session.pk
    )
    if session.status == UploadSession.Status.COMPLETED:
        raise Conflict("Una subida completa no puede abortarse.", code="upload_completed")
    if session.status == UploadSession.Status.ABORTED:
        return session
    part_keys = list(session.parts.values_list("storage_key", flat=True))
    session.status = UploadSession.Status.ABORTED
    session.video.status = Video.Status.FAILED
    session.save(update_fields=("status", "updated_at"))
    session.video.save(update_fields=("status", "updated_at"))
    transaction.on_commit(lambda: _delete_part_files(part_keys))
    return session
