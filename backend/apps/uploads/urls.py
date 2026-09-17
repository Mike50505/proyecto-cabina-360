from django.urls import path

from .views import (
    UploadAbortView,
    UploadCompleteView,
    UploadCreateView,
    UploadDetailView,
    UploadPartView,
)

urlpatterns = [
    path("uploads/", UploadCreateView.as_view(), name="upload-create"),
    path("uploads/<uuid:upload_id>/", UploadDetailView.as_view(), name="upload-detail"),
    path(
        "uploads/<uuid:upload_id>/parts/<int:number>/",
        UploadPartView.as_view(),
        name="upload-part",
    ),
    path(
        "uploads/<uuid:upload_id>/complete/",
        UploadCompleteView.as_view(),
        name="upload-complete",
    ),
    path(
        "uploads/<uuid:upload_id>/abort/",
        UploadAbortView.as_view(),
        name="upload-abort",
    ),
]

