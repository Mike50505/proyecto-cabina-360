from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import EventVideoListView, VideoViewSet

router = SimpleRouter()
router.register("videos", VideoViewSet, basename="video")

urlpatterns = [
    path("events/<uuid:event_id>/videos/", EventVideoListView.as_view(), name="event-video-list"),
    path("", include(router.urls)),
]

