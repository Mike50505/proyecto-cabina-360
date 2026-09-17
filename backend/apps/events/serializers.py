from django.conf import settings
from rest_framework import serializers

from apps.operators.services import membership_for_user

from .models import Event, EventType, ReservedVideoToken
from .services import DEFAULT_TOKEN_POOL_SIZE, create_event


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ("id", "code", "name", "icon")


class EventSettingsSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=("720p", "1080p", "4K"))
    camera_id = serializers.CharField(max_length=180)
    bitrate_mode = serializers.ChoiceField(
        choices=("AUTOMATIC", "LOW", "MEDIUM", "HIGH", "ADVANCED"),
        default="AUTOMATIC",
    )
    bitrate = serializers.IntegerField(min_value=500_000, max_value=100_000_000, required=False)
    duration_seconds = serializers.IntegerField(min_value=3, max_value=120)
    countdown_seconds = serializers.IntegerField(min_value=0, max_value=30, default=3)
    orientation = serializers.ChoiceField(choices=("PORTRAIT", "LANDSCAPE"))

    def validate(self, attrs):
        if attrs["bitrate_mode"] == "ADVANCED" and "bitrate" not in attrs:
            raise serializers.ValidationError(
                {"bitrate": "Es obligatorio en el modo avanzado."}
            )
        if attrs["bitrate_mode"] != "ADVANCED":
            attrs.pop("bitrate", None)
        return attrs


class ReservedVideoTokenSerializer(serializers.ModelSerializer):
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = ReservedVideoToken
        fields = ("id", "public_token", "public_url", "status")

    def get_public_url(self, obj):
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/v/{obj.public_token}/"


class EventSerializer(serializers.ModelSerializer):
    event_type = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.filter(is_active=True)
    )
    event_type_detail = EventTypeSerializer(source="event_type", read_only=True)
    settings = EventSettingsSerializer()
    public_url = serializers.SerializerMethodField()
    reserved_video_tokens = ReservedVideoTokenSerializer(
        source="video_tokens", many=True, read_only=True
    )
    token_pool_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=DEFAULT_TOKEN_POOL_SIZE,
        write_only=True,
    )

    class Meta:
        model = Event
        fields = (
            "id",
            "name",
            "description",
            "event_type",
            "event_type_detail",
            "event_date",
            "status",
            "settings",
            "settings_version",
            "public_token",
            "public_url",
            "public_access_enabled",
            "started_at",
            "finished_at",
            "retention_until",
            "created_at",
            "updated_at",
            "token_pool_size",
            "reserved_video_tokens",
        )
        read_only_fields = (
            "status",
            "settings_version",
            "public_token",
            "started_at",
            "finished_at",
            "retention_until",
            "created_at",
            "updated_at",
        )

    def get_public_url(self, obj):
        return f"{settings.EVENT_BASE_URL.rstrip('/')}/{obj.public_token}/"

    def create(self, validated_data):
        token_pool_size = validated_data.pop("token_pool_size")
        membership = membership_for_user(self.context["request"].user)
        return create_event(
            operator=membership.operator,
            validated_data=validated_data,
            token_pool_size=token_pool_size,
        )

    def update(self, instance, validated_data):
        if "settings" in validated_data and validated_data["settings"] != instance.settings:
            instance.settings_version += 1
        return super().update(instance, validated_data)


class EventSummarySerializer(EventSerializer):
    class Meta(EventSerializer.Meta):
        fields = tuple(
            field
            for field in EventSerializer.Meta.fields
            if field not in {"token_pool_size", "reserved_video_tokens"}
        )


class TokenReservationRequestSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=100)
