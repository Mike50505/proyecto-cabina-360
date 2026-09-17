import uuid

from django.db import models

from apps.operators.models import Operator

from .tokens import generate_public_token


class EventType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=60, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        ACTIVE = "ACTIVE", "Activo"
        FINISHED = "FINISHED", "Finalizado"
        EXPIRED = "EXPIRED", "Expirado"
        PENDING_DELETE = "PENDING_DELETE", "Pendiente de eliminación"
        DELETED = "DELETED", "Eliminado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.PROTECT, related_name="events")
    event_type = models.ForeignKey(
        EventType, on_delete=models.PROTECT, related_name="events"
    )
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    event_date = models.DateTimeField()
    cover_storage_key = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    public_token = models.CharField(
        max_length=64, unique=True, default=generate_public_token, editable=False
    )
    public_access_enabled = models.BooleanField(default=True)
    settings = models.JSONField(default=dict)
    settings_version = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-event_date", "-created_at")
        indexes = [
            models.Index(fields=("operator", "status")),
            models.Index(fields=("retention_until",)),
        ]

    def __str__(self) -> str:
        return self.name


class ReservedVideoToken(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponible para asignar"
        ASSIGNED = "ASSIGNED", "Asignado a una grabación"
        READY = "READY", "Video disponible"
        EXPIRED = "EXPIRED", "Expirado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="video_tokens")
    public_token = models.CharField(
        max_length=64, unique=True, default=generate_public_token, editable=False
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AVAILABLE
    )
    assigned_video_uuid = models.UUIDField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("event", "status"))]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.status}"

