from django.contrib import admin

from .models import Device, Operator, OperatorMembership


class MembershipInline(admin.TabularInline):
    model = OperatorMembership
    extra = 0
    autocomplete_fields = ("user",)


class DeviceInline(admin.TabularInline):
    model = Device
    extra = 0
    readonly_fields = ("installation_id", "registered_by", "last_seen_at", "created_at")
    fields = ("name", "installation_id", "registered_by", "is_active", "last_seen_at")
    can_delete = False


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")
    inlines = (MembershipInline, DeviceInline)


@admin.register(OperatorMembership)
class OperatorMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "operator", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "operator__name")
    autocomplete_fields = ("user", "operator")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "operator",
        "platform",
        "app_version",
        "is_active",
        "last_seen_at",
    )
    list_filter = ("platform", "is_active")
    search_fields = ("name", "operator__name", "installation_id")
    autocomplete_fields = ("operator", "registered_by")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")

