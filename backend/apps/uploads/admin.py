from django.contrib import admin

from .models import UploadPart, UploadSession


class UploadPartInline(admin.TabularInline):
    model = UploadPart
    extra = 0
    can_delete = False
    readonly_fields = ("number", "offset", "size_bytes", "sha256", "storage_key", "created_at")


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "video",
        "operator",
        "status",
        "received_bytes",
        "expected_size_bytes",
        "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "video__id", "operator__name", "idempotency_key")
    autocomplete_fields = ("video", "operator")
    readonly_fields = (
        "idempotency_key",
        "received_bytes",
        "error_code",
        "completed_at",
        "created_at",
        "updated_at",
    )
    inlines = (UploadPartInline,)

