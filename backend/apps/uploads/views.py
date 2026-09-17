import re

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.operators.permissions import IsActiveOperatorMember
from apps.operators.services import membership_for_user

from .models import UploadSession
from .parsers import OctetStreamParser
from .serializers import UploadCreateSerializer, UploadSessionSerializer
from .services import (
    abort_upload_session,
    complete_upload_session,
    create_upload_session,
    store_upload_part,
)

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class OperatorUploadMixin:
    permission_classes = (IsAuthenticated, IsActiveOperatorMember)

    def get_upload(self, request, upload_id):
        membership = membership_for_user(request.user)
        return get_object_or_404(
            UploadSession.objects.select_related(
                "video", "video__event", "video__token_reservation"
            ).prefetch_related("parts"),
            pk=upload_id,
            operator=membership.operator,
        )


class UploadCreateView(OperatorUploadMixin, APIView):
    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            return Response(
                {
                    "error": {
                        "code": "IDEMPOTENCY_KEY_REQUIRED",
                        "message": "Idempotency-Key es obligatorio.",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = UploadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = membership_for_user(request.user)
        session, created = create_upload_session(
            operator=membership.operator,
            data=serializer.validated_data,
            idempotency_key=idempotency_key,
        )
        return Response(
            UploadSessionSerializer(session).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UploadDetailView(OperatorUploadMixin, APIView):
    def get(self, request, upload_id):
        return Response(UploadSessionSerializer(self.get_upload(request, upload_id)).data)


class UploadPartView(OperatorUploadMixin, APIView):
    parser_classes = (OctetStreamParser,)

    def put(self, request, upload_id, number):
        claimed_sha256 = request.headers.get("X-Part-SHA256", "").strip().lower()
        if claimed_sha256 and not SHA256_PATTERN.fullmatch(claimed_sha256):
            return Response(
                {
                    "error": {
                        "code": "INVALID_PART_SHA256",
                        "message": "X-Part-SHA256 no es válido.",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        part, created = store_upload_part(
            session=self.get_upload(request, upload_id),
            number=number,
            stream=request.data,
            claimed_sha256=claimed_sha256,
        )
        return Response(
            {
                "number": part.number,
                "offset": part.offset,
                "size_bytes": part.size_bytes,
                "sha256": part.sha256,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UploadCompleteView(OperatorUploadMixin, APIView):
    def post(self, request, upload_id):
        session = complete_upload_session(self.get_upload(request, upload_id))
        return Response(UploadSessionSerializer(session).data)


class UploadAbortView(OperatorUploadMixin, APIView):
    def post(self, request, upload_id):
        session = abort_upload_session(self.get_upload(request, upload_id))
        return Response(UploadSessionSerializer(session).data)

