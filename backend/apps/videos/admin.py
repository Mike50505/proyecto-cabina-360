from django.contrib import admin

from .models import PublicVideoAccess, Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event",
        "operator",
        "status",
        "size_bytes",
        "mime_type",
        "uploaded_at",
    )
    list_filter = ("status", "mime_type", "storage_backend")
    search_fields = ("id", "event__name", "operator__name", "checksum_sha256")
    autocomplete_fields = ("event", "operator", "token_reservation")
    readonly_fields = (
        "storage_key",
        "thumbnail_storage_key",
        "checksum_sha256",
        "uploaded_at",
        "created_at",
        "updated_at",
    )


@admin.register(PublicVideoAccess)
class PublicVideoAccessAdmin(admin.ModelAdmin):
    list_display = ("video", "action", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("video__id", "video__event__name")
    readonly_fields = ("video", "action", "ip_hash", "user_agent", "created_at")
