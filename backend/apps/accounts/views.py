import logging

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.operators.services import membership_for_user

from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    OperatorSummarySerializer,
    RefreshSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if response.status_code >= 400:
            logger.warning(
                "login_failed",
                extra={"metadata": {"status_code": response.status_code}},
            )
        return response


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = RefreshSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError as exc:
            raise serializers.ValidationError(
                {"refresh": "El refresh token no es válido."},
                code="invalid_refresh_token",
            ) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        membership = membership_for_user(request.user)
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "operator": OperatorSummarySerializer(membership).data,
            }
        )
