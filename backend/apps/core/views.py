import os
from pathlib import Path

from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        checks = {"database": False, "storage": False}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks["database"] = cursor.fetchone() == (1,)
        except Exception:
            checks["database"] = False

        try:
            storage_root = Path(settings.MEDIA_ROOT)
            storage_root.mkdir(parents=True, exist_ok=True)
            checks["storage"] = storage_root.is_dir() and os.access(storage_root, os.W_OK)
        except OSError:
            checks["storage"] = False

        healthy = all(checks.values())
        return Response(
            {"status": "ok" if healthy else "unhealthy", "checks": checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

