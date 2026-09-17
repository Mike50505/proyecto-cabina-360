from rest_framework.permissions import BasePermission

from .services import membership_for_user


class IsActiveOperatorMember(BasePermission):
    def has_permission(self, request, view):
        membership_for_user(request.user)
        return True

