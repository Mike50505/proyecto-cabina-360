from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import EventTypeListView, EventViewSet

router = SimpleRouter()
router.register("events", EventViewSet, basename="event")

urlpatterns = [
    path("event-types/", EventTypeListView.as_view(), name="event-type-list"),
    path("", include(router.urls)),
]

