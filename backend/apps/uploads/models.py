import uuid

from django.db import models
from django.db.models import Q

from apps.operators.models import Operator
from apps.videos.models import Video


class UploadSession(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Creada"
        RECEIVING = "RECEIVING", "Recibiendo"
        VERIFYING = "VERIFYING", "Verificando"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallida"
        ABORTED = "ABORTED", "Abortada"
        EXPIRED = "EXPIRED", "Expirada"

    ACTIVE_STATUSES = (Status.CREATED, Status.RECEIVING, Status.VERIFYING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(
        Operator, on_delete=models.PROTECT, related_name="upload_sessions"
    )
    video = models.ForeignKey(
        Video, on_delete=models.PROTECT, related_name="upload_sessions"
    )
    idempotency_key = models.CharField(max_length=128)
    expected_size_bytes = models.PositiveBigIntegerField()
    expected_sha256 = models.CharField(max_length=64)
    part_size_bytes = models.PositiveIntegerField()
    received_bytes = models.PositiveBigIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED
    )
    error_code = models.CharField(max_length=80, blank=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("operator", "idempotency_key"),
                name="unique_upload_idempotency_key_per_operator",
            ),
            models.UniqueConstraint(
                fields=("video",),
                condition=Q(status__in=("CREATED", "RECEIVING", "VERIFYING")),
                name="unique_active_upload_per_video",
            ),
        ]
        indexes = [models.Index(fields=("status", "expires_at"))]

    def __str__(self) -> str:
        return f"{self.video_id} · {self.status}"


class UploadPart(models.Model):
    id = models.BigAutoField(primary_key=True)
    session = models.ForeignKey(
        UploadSession, on_delete=models.CASCADE, related_name="parts"
    )
    number = models.PositiveIntegerField()
    offset = models.PositiveBigIntegerField()
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    storage_key = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("number",)
        constraints = [
            models.UniqueConstraint(
                fields=("session", "number"), name="unique_part_number_per_upload"
            )
        ]

    def __str__(self) -> str:
        return f"{self.session_id} · {self.number}"

