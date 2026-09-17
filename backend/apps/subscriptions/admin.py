from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "currency",
        "retention_days",
        "max_devices",
        "is_active",
    )
    list_filter = ("is_active", "branding_enabled")
    search_fields = ("name", "code")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "operator",
        "plan",
        "status",
        "provider",
        "starts_at",
        "expires_at",
        "is_current",
    )
    list_filter = ("status", "provider", "is_current", "plan")
    search_fields = ("operator__name", "provider_reference")
    autocomplete_fields = ("operator", "plan")
    date_hierarchy = "expires_at"

    def save_model(self, request, obj, form, change):
        if obj.is_current:
            Subscription.objects.filter(
                operator=obj.operator, is_current=True
            ).exclude(pk=obj.pk).update(is_current=False)
        obj.full_clean()
        super().save_model(request, obj, form, change)

