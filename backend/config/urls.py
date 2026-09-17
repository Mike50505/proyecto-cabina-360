from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.operators.urls")),
    path("api/v1/", include("apps.subscriptions.urls")),
    path("api/v1/", include("apps.events.api_urls")),
    path("api/v1/", include("apps.videos.urls")),
    path("api/v1/", include("apps.uploads.urls")),
    path("", include("apps.events.public_urls")),
]
