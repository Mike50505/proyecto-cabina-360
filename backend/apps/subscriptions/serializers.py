from rest_framework import serializers

from .models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "code",
            "name",
            "price",
            "currency",
            "max_events_per_month",
            "retention_days",
            "max_storage_bytes",
            "max_devices",
            "branding_enabled",
            "features",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    grants_access = serializers.BooleanField(read_only=True)
    usage = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            "id",
            "status",
            "provider",
            "starts_at",
            "expires_at",
            "grants_access",
            "plan",
            "usage",
        )

    def get_usage(self, obj):
        return {
            "events_this_month": 0,
            "storage_bytes": 0,
            "active_devices": obj.operator.devices.filter(is_active=True).count(),
        }

