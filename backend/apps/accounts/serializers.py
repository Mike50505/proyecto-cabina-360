from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

from apps.operators.services import membership_for_user


class OperatorSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="operator.id")
    name = serializers.CharField(source="operator.name")
    role = serializers.CharField()


class UserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        membership = membership_for_user(user)
        token["operator_id"] = str(membership.operator_id)
        token["role"] = membership.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        membership = membership_for_user(self.user)
        data["user"] = UserSerializer(self.user).data
        data["operator"] = OperatorSummarySerializer(membership).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class RefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = RefreshToken(attrs["refresh"])
        try:
            user = User.objects.get(pk=token["user_id"], is_active=True)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"refresh": "La sesión ya no está activa."}, code="user_inactive"
            ) from exc
        membership_for_user(user)
        return super().validate(attrs)
