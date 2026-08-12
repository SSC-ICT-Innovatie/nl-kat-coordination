from django.conf import settings
from katalogus.client import get_katalogus_client
from katalogus.exceptions import KATalogusException
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from structlog import get_logger

from octopoes.connector.octopoes import OctopoesAPIConnector
from rocky.exceptions import OctopoesException
from rocky.signals import _get_healthy_katalogus, _get_healthy_octopoes
from tools.models import Indemnification, Organization
from tools.permissions import CanRecalculateBits, CanSetKatalogusSettings
from tools.serializers import OrganizationSerializer, OrganizationSerializerReadOnlyCode, ToOrganizationSerializer

logger = get_logger(__name__)


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    # When we created this viewset we didn't have pagination enabled in the
    # django-rest-framework settings. Enabling it afterwards would cause the API
    # to change in an incompatible way, we should enable this when we introduce
    # a new API version.
    pagination_class = None

    # Unfortunately django-rest-framework doesn't have support for create only
    # fields so we have to change the serializer class depending on the request
    # method.
    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.request.method != "POST":
            serializer_class = OrganizationSerializerReadOnlyCode
        return serializer_class

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        katalogus_client = _get_healthy_katalogus()
        octopoes_client = _get_healthy_octopoes(instance.code)

        try:
            octopoes_client.delete_node()
        except Exception as e:
            raise OctopoesException("Failed deleting organization in Octopoes") from e

        try:
            katalogus_client.delete_organization(instance.code)
        except Exception as e:
            try:
                octopoes_client.create_node()
            except Exception as second_exception:
                raise OctopoesException("Failed creating organization in Octopoes") from second_exception

            raise KATalogusException("Failed deleting organization in the Katalogus") from e

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, permission_classes=[])
    def indemnification(self, request, pk=None):
        # DRF does not support different arguments when mapping POST/GET of the
        # same endpoint to a different method, so we can't use the
        # permission_classes argument here.
        if not request.user.has_perm("tools.view_organization"):
            raise PermissionDenied()

        organization = self.get_object()
        indemnification = Indemnification.objects.filter(organization=organization).first()

        if indemnification:
            return Response({"indemnification": True, "user": indemnification.user.pk})
        else:
            return Response({"indemnification": False, "user": None})

    @indemnification.mapping.post
    def set_indemnification(self, request, pk=None):
        if not request.user.has_perm("tools.add_indemnification"):
            raise PermissionDenied()

        organization = self.get_object()

        indemnification = Indemnification.objects.filter(organization=organization).first()
        if indemnification:
            return Response({"indemnification": True, "user": indemnification.user.pk}, status=status.HTTP_409_CONFLICT)

        indemnification = Indemnification.objects.create(organization=organization, user=self.request.user)

        return Response({"indemnification": True, "user": indemnification.user.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[CanRecalculateBits])
    def recalculate_bits(self, request, pk=None):
        organization = self.get_object()
        logger.info("Recalculating bits", event_code=920000, organization_code=organization.code)
        connector = OctopoesAPIConnector(
            settings.OCTOPOES_API, organization.code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
        )
        number_of_bits = connector.recalculate_bits()

        return Response({"number_of_bits": number_of_bits})

    @action(detail=True, methods=["post"], permission_classes=[CanSetKatalogusSettings])
    def clone_katalogus_settings(self, request, pk=None):
        from_organization = self.get_object()

        serializer = ToOrganizationSerializer(data=request.data)
        if serializer.is_valid():
            to_organization = serializer.validated_data["to_organization"]
            get_katalogus_client().clone_all_configuration_to_organization(from_organization.code, to_organization.code)

            return Response()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
