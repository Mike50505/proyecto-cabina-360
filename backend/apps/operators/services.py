from rest_framework.exceptions import AuthenticationFailed

from .models import OperatorMembership


def membership_for_user(user) -> OperatorMembership:
    membership = (
        OperatorMembership.objects.select_related("operator")
        .filter(user=user, is_active=True, operator__is_active=True)
        .order_by("created_at")
        .first()
    )
    if membership is None:
        raise AuthenticationFailed(
            "Tu cuenta no está asociada a un operador activo.",
            code="operator_inactive",
        )
    return membership

