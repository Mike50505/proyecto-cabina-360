from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.subscriptions.permissions import HasActiveSubscription

from .models import Device
from .serializers import DeviceSerializer
from .services import membership_for_user


class DeviceListCreateView(ListCreateAPIView):
    serializer_class = DeviceSerializer
    permission_classes = (IsAuthenticated, HasActiveSubscription)

    def get_queryset(self):
        membership = membership_for_user(self.request.user)
        return Device.objects.filter(operator=membership.operator)
