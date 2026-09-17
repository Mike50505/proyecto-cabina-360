from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.events.models import Event
from apps.operators.permissions import IsActiveOperatorMember
from apps.operators.services import membership_for_user

from .models import Video
from .serializers import VideoSerializer
from .services import delete_video


class VideoViewSet(
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = VideoSerializer
    permission_classes = (IsAuthenticated, IsActiveOperatorMember)
    lookup_field = "id"

    def get_queryset(self):
        membership = membership_for_user(self.request.user)
        return Video.objects.select_related("token_reservation", "event").filter(
            operator=membership.operator
        )

    def perform_destroy(self, instance):
        delete_video(instance)


class EventVideoListView(ListAPIView):
    serializer_class = VideoSerializer
    permission_classes = (IsAuthenticated, IsActiveOperatorMember)

    def get_queryset(self):
        membership = membership_for_user(self.request.user)
        event = get_object_or_404(
            Event.objects,
            pk=self.kwargs["event_id"], operator=membership.operator
        )
        return Video.objects.select_related("token_reservation").filter(event=event)
