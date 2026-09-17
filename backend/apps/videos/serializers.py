from django.conf import settings
from rest_framework import serializers

from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    public_token = serializers.CharField(read_only=True)
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = (
            "id",
            "event_id",
            "original_filename",
            "size_bytes",
            "expected_size_bytes",
            "mime_type",
            "duration_ms",
            "checksum_sha256",
            "status",
            "public_token",
            "public_url",
            "uploaded_at",
            "expires_at",
            "created_at",
            "updated_at",
        )

    def get_public_url(self, obj):
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/v/{obj.public_token}/"

