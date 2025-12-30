from http import HTTPStatus
from typing import Any

import structlog
from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.viewsets import ViewSet

from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSCNAMERecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSPTRRecord,
    DNSSRVRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    ObjectTask,
    Software,
)
from objects.serializers import (
    DNSAAAARecordSerializer,
    DNSARecordSerializer,
    DNSCAARecordSerializer,
    DNSCNAMERecordSerializer,
    DNSMXRecordSerializer,
    DNSNSRecordSerializer,
    DNSPTRRecordSerializer,
    DNSSRVRecordSerializer,
    DNSTXTRecordSerializer,
    FindingSerializer,
    FindingTypeSerializer,
    HostnameSerializer,
    IPAddressSerializer,
    IPPortSerializer,
    NetworkSerializer,
    SoftwareSerializer,
)
from openkat.permissions import KATMultiModelPermissions
from openkat.viewsets import ManyModelViewSet
from tasks.models import Task

logger = structlog.getLogger(__name__)


class ObjectTaskResultMixin:
    def perform_create(self, serializer):
        results = serializer.save()

        if (
            hasattr(self.request, "auth")  # type: ignore[attr-defined]
            and isinstance(self.request.auth, dict)  # type: ignore[attr-defined]
            and self.request.auth.get("task_id") is not None  # type: ignore[attr-defined]
        ):
            task = Task.objects.get(pk=self.request.auth.get("task_id"))  # type: ignore[attr-defined]
            if not isinstance(results, list):
                results = [results]

            object_tasks = []
            for result in results:
                object_tasks.append(
                    ObjectTask(
                        task_id=str(task.pk),  # Convert UUID to string for XTDB
                        type=task.type,
                        plugin_id=task.data.get("plugin_id"),
                        output_object=result.pk,
                        output_object_type=str(result.__class__.__name__).lower(),
                    )
                )
            ObjectTask.objects.bulk_create(object_tasks)


class ObjectViewSet(ViewSet, ObjectTaskResultMixin):
    permission_classes = (KATMultiModelPermissions,)
    serializers = (
        HostnameSerializer,
        IPAddressSerializer,
        IPPortSerializer,
        NetworkSerializer,
        DNSAAAARecordSerializer,
        DNSARecordSerializer,
        DNSCAARecordSerializer,
        DNSCNAMERecordSerializer,
        DNSMXRecordSerializer,
        DNSNSRecordSerializer,
        DNSPTRRecordSerializer,
        DNSSRVRecordSerializer,
        DNSTXTRecordSerializer,
    )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> JsonResponse:
        serializers = {serializer.Meta.model.__name__.lower(): serializer for serializer in self.serializers}
        response = {}

        for object_type, serializer_class in serializers.items():
            if object_type not in request.data:
                continue

            models = request.data[object_type]
            serializer = serializer_class(data=models, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            response[object_type] = serializer.data

        return JsonResponse(status=HTTPStatus.CREATED, data=response)

    @action(detail=False, methods=("post",), url_path="delete")
    def delete_with_post(self, request: Request, *args: Any, **kwargs: Any) -> JsonResponse:
        serializers = {serializer.Meta.model.__name__.lower(): serializer for serializer in self.serializers}
        deleted = {}
        total = 0

        for object_type, ids in request.data.items():
            if not isinstance(object_type, str):
                continue

            if object_type not in serializers:
                continue

            if not isinstance(ids, list):
                continue

            model_cls = serializers[object_type].Meta.model
            qs = model_cls.objects.filter(id__in=ids)
            count = qs.count()
            if count > 0:
                qs.delete()
            deleted[object_type] = count
            total += count

        return JsonResponse(status=HTTPStatus.OK, data={"deleted": deleted, "total": total})


class FindingTypeViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = FindingTypeSerializer
    queryset = FindingType.objects.all()
    filterset_fields = ("code",)


class FindingViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = FindingSerializer
    queryset = Finding.objects.all()


class NetworkViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = NetworkSerializer
    queryset = Network.objects.all()
    filterset_fields = ("name",)


class HostnameViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = HostnameSerializer
    queryset = Hostname.objects.prefetch_related(
        "dnsarecord_set",
        "dnsaaaarecord_set",
        "dnscnamerecord_set",
        "dnsmxrecord_set",
        "dnsnsrecord_set",
        "dnsptrrecord_set",
        "dnscaarecord_set",
        "dnstxtrecord_set",
        "dnssrvrecord_set",
    )
    filterset_fields = ("name",)


class IPAddressViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = IPAddressSerializer
    queryset = IPAddress.objects.all()
    filterset_fields = ("ip_address",)


class IPPortViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = IPPortSerializer
    queryset = IPPort.objects.all()
    filterset_fields = ("ip_address", "protocol", "port", "tls", "service")


class SoftwareViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = SoftwareSerializer
    queryset = Software.objects.all()
    filterset_fields = ("name", "version", "cpi", "ports")


class DNSARecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSARecordSerializer
    queryset = DNSARecord.objects.all()


class DNSAAAARecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSAAAARecordSerializer
    queryset = DNSAAAARecord.objects.all()


class DNSPTRRecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSPTRRecordSerializer
    queryset = DNSPTRRecord.objects.all()


class DNSCNAMERecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSCNAMERecordSerializer
    queryset = DNSCNAMERecord.objects.all()


class DNSMXRecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSMXRecordSerializer
    queryset = DNSMXRecord.objects.all()


class DNSNSRecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSNSRecordSerializer
    queryset = DNSNSRecord.objects.all()


class DNSCAARecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSCAARecordSerializer
    queryset = DNSCAARecord.objects.all()


class DNSTXTRecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSTXTRecordSerializer
    queryset = DNSTXTRecord.objects.all()


class DNSSRVRecordViewSet(ObjectTaskResultMixin, ManyModelViewSet):
    serializer_class = DNSSRVRecordSerializer
    queryset = DNSSRVRecord.objects.all()
