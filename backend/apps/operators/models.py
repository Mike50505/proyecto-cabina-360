import uuid

from django.conf import settings
from django.db import models


class Operator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class OperatorMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Propietario"
        EMPLOYEE = "EMPLOYEE", "Empleado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(
        Operator, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="operator_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("operator", "user"), name="unique_operator_user_membership"
            )
        ]
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.user.email} · {self.operator.name}"


class Device(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "ANDROID", "Android"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="devices")
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registered_devices",
    )
    installation_id = models.UUIDField(unique=True)
    name = models.CharField(max_length=120)
    platform = models.CharField(
        max_length=20, choices=Platform.choices, default=Platform.ANDROID
    )
    app_version = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_seen_at", "-created_at")

    def __str__(self) -> str:
        return f"{self.name} · {self.operator.name}"

