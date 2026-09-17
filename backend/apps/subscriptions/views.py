from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operators.services import membership_for_user

from .serializers import SubscriptionSerializer
from .services import current_subscription


class SubscriptionView(APIView):
    def get(self, request):
        membership = membership_for_user(request.user)
        subscription = current_subscription(membership.operator)
        if subscription is None:
            return Response(
                {
                    "status": "NONE",
                    "grants_access": False,
                    "plan": None,
                    "usage": {
                        "events_this_month": 0,
                        "storage_bytes": 0,
                        "active_devices": membership.operator.devices.filter(
                            is_active=True
                        ).count(),
                    },
                }
            )
        return Response(SubscriptionSerializer(subscription).data)

