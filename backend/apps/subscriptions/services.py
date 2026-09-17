from rest_framework.exceptions import PermissionDenied

from apps.operators.models import Operator

from .models import Subscription


def current_subscription(operator: Operator) -> Subscription | None:
    return (
        Subscription.objects.select_related("plan")
        .filter(operator=operator, is_current=True)
        .first()
    )


def require_active_subscription(operator: Operator) -> Subscription:
    subscription = current_subscription(operator)
    if subscription is None or not subscription.grants_access:
        raise PermissionDenied(
            "Necesitas una suscripción activa para realizar esta operación.",
            code="subscription_inactive",
        )
    return subscription

