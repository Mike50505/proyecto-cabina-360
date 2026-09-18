from django.urls import path

from .views import public_download, public_event, public_stream, public_thumbnail, public_video

urlpatterns = [
    path("e/<str:token>/", public_event, name="public-event"),
    path("v/<str:token>/", public_video, name="public-video"),
    path("v/<str:token>/thumbnail/", public_thumbnail, name="public-video-thumbnail"),
    path("v/<str:token>/stream/", public_stream, name="public-video-stream"),
    path("v/<str:token>/download/", public_download, name="public-video-download"),
]
