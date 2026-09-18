import hashlib
import re

from django.conf import settings
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operators.permissions import IsActiveOperatorMember
from apps.operators.services import membership_for_user
from apps.subscriptions.permissions import HasActiveSubscription
from apps.storage.service import StorageService
from apps.videos.models import PublicVideoAccess, Video

from .models import Event, EventType, ReservedVideoToken
from .serializers import (
    EventSerializer,
    EventSummarySerializer,
    EventTypeSerializer,
    ReservedVideoTokenSerializer,
    TokenReservationRequestSerializer,
)
from .services import finish_event, reserve_video_tokens, start_event


class EventTypeListView(APIView):
    def get(self, request):
        return Response(EventTypeSerializer(EventType.objects.filter(is_active=True), many=True).data)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    lookup_field = "id"

    def get_queryset(self):
        membership = membership_for_user(self.request.user)
        queryset = Event.objects.select_related("event_type").filter(
            operator=membership.operator
        )
        if self.action != "list":
            queryset = queryset.prefetch_related("video_tokens")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return EventSummarySerializer
        return EventSerializer

    def get_permissions(self):
        permissions = [IsActiveOperatorMember()]
        if self.action in {"create", "update", "partial_update", "start", "reserve_tokens"}:
            permissions.append(HasActiveSubscription())
        return permissions

    def perform_destroy(self, instance):
        instance.status = Event.Status.DELETED
        instance.public_access_enabled = False
        instance.save(update_fields=("status", "public_access_enabled", "updated_at"))

    @action(detail=True, methods=("post",))
    def start(self, request, id=None):
        event = start_event(self.get_object())
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=("post",))
    def finish(self, request, id=None):
        event = finish_event(self.get_object())
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=("post",), url_path="video-tokens/reserve")
    def reserve_tokens(self, request, id=None):
        event = self.get_object()
        serializer = TokenReservationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = reserve_video_tokens(event, serializer.validated_data["quantity"])
        return Response(
            ReservedVideoTokenSerializer(
                tokens, many=True, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )


def _event_is_public(event: Event) -> bool:
    if not event.public_access_enabled:
        return False
    if event.status in {
        Event.Status.EXPIRED,
        Event.Status.PENDING_DELETE,
        Event.Status.DELETED,
    }:
        return False
    return not event.retention_until or event.retention_until > timezone.now()


def public_event(request, token: str):
    event = get_object_or_404(
        Event.objects.select_related("event_type"),
        public_token=token,
    )
    if not _event_is_public(event):
        return render(request, "public_gallery/unavailable.html", status=410)
    videos = event.videos.filter(status=Video.Status.READY).select_related("token_reservation")
    return render(request, "public_gallery/event.html", {"event": event, "videos": videos})


def _record_access(request, video: Video, action: str) -> None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip()
    address = forwarded or request.META.get("REMOTE_ADDR", "")
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{address}".encode()).hexdigest() if address else ""
    PublicVideoAccess.objects.create(
        video=video,
        action=action,
        ip_hash=digest,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )


def public_video(request, token: str):
    reservation = get_object_or_404(
        ReservedVideoToken.objects.select_related("event", "event__event_type"),
        public_token=token,
    )
    if not _event_is_public(reservation.event) or reservation.status == ReservedVideoToken.Status.EXPIRED:
        return render(request, "public_gallery/unavailable.html", status=410)
    video = getattr(reservation, "video", None)
    if video is None or video.status != Video.Status.READY:
        return render(
            request,
            "public_gallery/video_pending.html",
            {"event": reservation.event, "reservation": reservation},
        )
    _record_access(request, video, PublicVideoAccess.Action.VIEW)
    return render(request, "public_gallery/video.html", {"event": reservation.event, "video": video})


def public_thumbnail(request, token: str):
    reservation = get_object_or_404(
        ReservedVideoToken.objects.select_related("event", "video"), public_token=token
    )
    video = getattr(reservation, "video", None)
    if not _event_is_public(reservation.event) or video is None or video.status != Video.Status.READY:
        return HttpResponse(status=404)
    storage = StorageService()
    if not video.thumbnail_storage_key or not storage.provider.exists(video.thumbnail_storage_key):
        return HttpResponse(status=404)
    if settings.CADDY_ACCEL_REDIRECT_ENABLED:
        response = HttpResponse(content_type="image/jpeg")
        response["X-Accel-Redirect"] = f"/{video.thumbnail_storage_key}"
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    response = FileResponse(storage.provider.open(video.thumbnail_storage_key), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")


def _file_chunks(stream, start: int, length: int, chunk_size: int = 1024 * 1024):
    try:
        stream.seek(start)
        remaining = length
        while remaining:
            block = stream.read(min(chunk_size, remaining))
            if not block:
                break
            remaining -= len(block)
            yield block
    finally:
        stream.close()


def _video_bytes(request, token: str, *, download: bool):
    reservation = get_object_or_404(
        ReservedVideoToken.objects.select_related("event", "video"), public_token=token
    )
    video = getattr(reservation, "video", None)
    storage = StorageService()
    if (
        not _event_is_public(reservation.event)
        or video is None
        or video.status != Video.Status.READY
        or not video.storage_key
        or not storage.provider.exists(video.storage_key)
    ):
        return HttpResponse(status=404)

    if settings.CADDY_ACCEL_REDIRECT_ENABLED:
        response = HttpResponse(content_type=video.mime_type or "video/mp4")
        response["X-Accel-Redirect"] = f"/{video.storage_key}"
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        if download:
            response["Content-Disposition"] = content_disposition_header(
                True, video.original_filename or f"{video.id}.mp4"
            )
        _record_access(
            request,
            video,
            PublicVideoAccess.Action.DOWNLOAD if download else PublicVideoAccess.Action.STREAM,
        )
        return response

    size = storage.provider.size(video.storage_key)
    start, end = 0, size - 1
    status_code = 200
    range_header = request.headers.get("Range")
    if range_header:
        match = _RANGE_PATTERN.fullmatch(range_header.strip())
        if not match or (not match.group(1) and not match.group(2)):
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else end
        else:
            suffix = int(match.group(2))
            start = max(0, size - suffix)
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        end = min(end, size - 1)
        status_code = 206

    length = end - start + 1
    stream = storage.provider.open(video.storage_key)
    response = StreamingHttpResponse(
        _file_chunks(stream, start, length),
        status=status_code,
        content_type=video.mime_type or "video/mp4",
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(length)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    if status_code == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    if download:
        response["Content-Disposition"] = content_disposition_header(
            True, video.original_filename or f"{video.id}.mp4"
        )
    _record_access(
        request,
        video,
        PublicVideoAccess.Action.DOWNLOAD if download else PublicVideoAccess.Action.STREAM,
    )
    return response


def public_stream(request, token: str):
    return _video_bytes(request, token, download=False)


def public_download(request, token: str):
    return _video_bytes(request, token, download=True)
