import re

from django.conf import settings
from rest_framework import serializers

from apps.videos.serializers import VideoSerializer

from .models import UploadPart, UploadSession

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class UploadCreateSerializer(serializers.Serializer):
    video_uuid = serializers.UUIDField()
    event_uuid = serializers.UUIDField()
    public_video_token = serializers.CharField(min_length=32, max_length=64)
    original_filename = serializers.CharField(max_length=500)
    size_bytes = serializers.IntegerField(min_value=1)
    sha256 = serializers.CharField(min_length=64, max_length=64)
    mime_type = serializers.ChoiceField(choices=("video/mp4",))
    duration_ms = serializers.IntegerField(min_value=1, max_value=30 * 60 * 1000, required=False)

    def validate_size_bytes(self, value):
        if value > settings.MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError(
                "El archivo supera el máximo permitido.", code="upload_too_large"
            )
        return value

    def validate_sha256(self, value):
        if not SHA256_PATTERN.fullmatch(value):
            raise serializers.ValidationError(
                "Debe ser un SHA-256 hexadecimal.", code="invalid_sha256"
            )
        return value.lower()


class UploadPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadPart
        fields = ("number", "offset", "size_bytes", "sha256")


class UploadSessionSerializer(serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)
    received_parts = UploadPartSerializer(source="parts", many=True, read_only=True)

    class Meta:
        model = UploadSession
        fields = (
            "id",
            "video",
            "status",
            "expected_size_bytes",
            "part_size_bytes",
            "received_bytes",
            "received_parts",
            "error_code",
            "expires_at",
            "completed_at",
            "created_at",
            "updated_at",
        )

