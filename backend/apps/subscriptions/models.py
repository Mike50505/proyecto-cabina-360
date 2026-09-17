import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.operators.models import Operator


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="MXN")
    max_events_per_month = models.PositiveIntegerField(default=10)
    retention_days = models.PositiveIntegerField(default=30)
    max_storage_bytes = models.PositiveBigIntegerField(default=50 * 1024**3)
    max_devices = models.PositiveIntegerField(default=1)
    branding_enabled = models.BooleanField(default=False)
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("price", "name")

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Prueba"
        ACTIVE = "ACTIVE", "Activa"
        PAST_DUE = "PAST_DUE", "Pago pendiente"
        CANCELLED = "CANCELLED", "Cancelada"
        EXPIRED = "EXPIRED", "Expirada"

    class Provider(models.TextChoices):
        MANUAL = "MANUAL", "Manual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(
        Operator, on_delete=models.PROTECT, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.MANUAL
    )
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_current = models.BooleanField(default=True)
    provider_reference = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("operator",),
                condition=Q(is_current=True),
                name="unique_current_subscription_per_operator",
            )
        ]

    def clean(self):
        if self.expires_at <= self.starts_at:
            raise ValidationError({"expires_at": "Debe ser posterior al inicio."})

    @property
    def grants_access(self) -> bool:
        return (
            self.is_current
            and self.status in {self.Status.TRIAL, self.Status.ACTIVE}
            and self.plan.is_active
            and self.starts_at <= timezone.now() < self.expires_at
        )

    def __str__(self) -> str:
        return f"{self.operator} · {self.plan} · {self.status}"
