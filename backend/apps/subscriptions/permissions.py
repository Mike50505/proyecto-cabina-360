from rest_framework.permissions import BasePermission

from apps.operators.services import membership_for_user

from .services import current_subscription


class HasActiveSubscription(BasePermission):
    message = "Necesitas una suscripción activa para realizar esta operación."
    code = "subscription_inactive"

    def has_permission(self, request, view):
        membership = membership_for_user(request.user)
        subscription = current_subscription(membership.operator)
        return subscription is not None and subscription.grants_access

