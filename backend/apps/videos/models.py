import uuid

from django.db import models

from apps.events.models import Event, ReservedVideoToken
from apps.operators.models import Operator


class Video(models.Model):
    class Status(models.TextChoices):
        PENDING_UPLOAD = "PENDING_UPLOAD", "Pendiente de subida"
        UPLOADING = "UPLOADING", "Subiendo"
        VERIFYING = "VERIFYING", "Verificando"
        UPLOADED = "UPLOADED", "Subido"
        PROCESSING = "PROCESSING", "Procesando"
        READY = "READY", "Disponible"
        FAILED = "FAILED", "Fallido"
        CORRUPT = "CORRUPT", "Corrupto"
        EXPIRED = "EXPIRED", "Expirado"
        PENDING_DELETE = "PENDING_DELETE", "Pendiente de eliminación"
        DELETED = "DELETED", "Eliminado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.PROTECT, related_name="videos")
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="videos")
    token_reservation = models.OneToOneField(
        ReservedVideoToken,
        on_delete=models.PROTECT,
        related_name="video",
    )
    original_filename = models.CharField(max_length=255)
    storage_backend = models.CharField(max_length=30, default="local")
    storage_key = models.CharField(max_length=500, blank=True)
    thumbnail_storage_key = models.CharField(max_length=500, blank=True)
    expected_size_bytes = models.PositiveBigIntegerField()
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    expected_sha256 = models.CharField(max_length=64)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING_UPLOAD
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("operator", "status")),
            models.Index(fields=("event", "created_at")),
            models.Index(fields=("expires_at",)),
        ]

    @property
    def public_token(self) -> str:
        return self.token_reservation.public_token

    def __str__(self) -> str:
        return f"{self.event.name} · {self.id}"

