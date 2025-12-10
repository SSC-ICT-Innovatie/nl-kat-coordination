from http import HTTPStatus
from typing import Any
from urllib.request import Request

from rest_framework import viewsets
from rest_framework.response import Response
from structlog import get_logger

from openkat.models import Organization
from openkat.serializers import OrganizationSerializer, OrganizationSerializerReadOnlyCode

logger = get_logger(__name__)


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.request.method != "POST":
            serializer_class = OrganizationSerializerReadOnlyCode
        return serializer_class


class ManyModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        if "id" in self.request.GET:
            return super().get_queryset().filter(id__in=self.request.GET.getlist("id"))

        return super().get_queryset()

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        count = queryset.count()

        if count == 0:
            return Response({"deleted": count}, status=HTTPStatus.OK)

        queryset.delete()

        return Response({"deleted": count}, status=HTTPStatus.OK)

    def get_serializer(self, *args, **kwargs):
        if isinstance(kwargs.get("data", {}), list):
            kwargs["many"] = True

        return super().get_serializer(*args, **kwargs)
