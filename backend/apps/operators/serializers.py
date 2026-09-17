from django.utils import timezone
from django.db import transaction
from rest_framework import serializers

from apps.subscriptions.services import require_active_subscription

from .models import Device, Operator
from .services import membership_for_user


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id",
            "installation_id",
            "name",
            "platform",
            "app_version",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "last_seen_at", "created_at")
        extra_kwargs = {"installation_id": {"validators": []}}

    def create(self, validated_data):
        request = self.context["request"]
        membership = membership_for_user(request.user)
        installation_id = validated_data.pop("installation_id")
        with transaction.atomic():
            operator = Operator.objects.select_for_update().get(pk=membership.operator_id)
            subscription = require_active_subscription(operator)
            device = Device.objects.select_for_update().filter(
                installation_id=installation_id
            ).first()
            if device is not None and device.operator_id != operator.id:
                raise serializers.ValidationError(
                    {"installation_id": "El identificador de instalación no es válido."},
                    code="invalid_installation_id",
                )
            if device is None:
                if operator.devices.filter(is_active=True).count() >= subscription.plan.max_devices:
                    raise serializers.ValidationError(
                        {"installation_id": "Tu plan alcanzó el límite de dispositivos."},
                        code="device_limit_reached",
                    )
                device = Device(installation_id=installation_id, operator=operator)

            for field, value in validated_data.items():
                setattr(device, field, value)
            device.registered_by = request.user
            device.last_seen_at = timezone.now()
            device.save()
        return device
