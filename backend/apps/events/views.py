from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operators.permissions import IsActiveOperatorMember
from apps.operators.services import membership_for_user
from apps.subscriptions.permissions import HasActiveSubscription

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
    event = get_object_or_404(Event.objects.select_related("event_type"), public_token=token)
    if not _event_is_public(event):
        return render(request, "public_gallery/unavailable.html", status=410)
    return render(request, "public_gallery/event.html", {"event": event})


def public_video(request, token: str):
    reservation = get_object_or_404(
        ReservedVideoToken.objects.select_related("event", "event__event_type"),
        public_token=token,
    )
    if not _event_is_public(reservation.event) or reservation.status == ReservedVideoToken.Status.EXPIRED:
        return render(request, "public_gallery/unavailable.html", status=410)
    return render(
        request,
        "public_gallery/video_pending.html",
        {"event": reservation.event, "reservation": reservation},
    )
