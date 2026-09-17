from django.contrib import admin

from .models import Event, EventType, ReservedVideoToken


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "code")


class ReservedVideoTokenInline(admin.TabularInline):
    model = ReservedVideoToken
    extra = 0
    fields = ("public_token", "status", "assigned_video_uuid", "created_at")
    readonly_fields = ("public_token", "created_at")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "operator",
        "event_type",
        "event_date",
        "status",
        "public_access_enabled",
        "retention_until",
    )
    list_filter = ("status", "event_type", "public_access_enabled")
    search_fields = ("name", "operator__name", "public_token")
    autocomplete_fields = ("operator", "event_type")
    readonly_fields = (
        "public_token",
        "settings_version",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "event_date"
    inlines = (ReservedVideoTokenInline,)


@admin.register(ReservedVideoToken)
class ReservedVideoTokenAdmin(admin.ModelAdmin):
    list_display = ("public_token", "event", "status", "assigned_video_uuid", "created_at")
    list_filter = ("status",)
    search_fields = ("public_token", "event__name", "assigned_video_uuid")
    autocomplete_fields = ("event",)
    readonly_fields = ("public_token", "created_at", "assigned_at")

