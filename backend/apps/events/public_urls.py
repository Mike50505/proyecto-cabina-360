from django.urls import path

from .views import public_event, public_video

urlpatterns = [
    path("e/<str:token>/", public_event, name="public-event"),
    path("v/<str:token>/", public_video, name="public-video"),
]

