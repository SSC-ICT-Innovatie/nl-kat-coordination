from collections.abc import Callable
from typing import Any

import structlog
from account.mixins import OrganizationView
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpRequest, JsonResponse
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from httpx import HTTPError
from katalogus.health import get_katalogus_health
from pydantic import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from octopoes.connector import ConnectorException
from octopoes.connector.octopoes import OctopoesAPIConnector
from rocky.bytes_client import get_bytes_client
from rocky.health import ServiceHealth
from rocky.scheduler import SchedulerError, scheduler_client
from rocky.version import __version__

logger = structlog.get_logger(__name__)


class Health(OrganizationView, View):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        octopoes_connector = self.octopoes_api_connector
        rocky_health = get_rocky_health(self.organization.code, octopoes_connector)
        return JsonResponse(rocky_health.model_dump())


class GlobalHealthView(APIView):
    """Non-org-scoped health endpoint for monitoring and load balancers (#4231).

    Public endpoint: checks all backing services without requiring an
    organization context. Returns 503 when any service is unhealthy so load
    balancers can take the instance out of rotation. The response is redacted
    to service + healthy only — no versions, additional, or per-org details
    that could fingerprint the installation.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        rocky_health = get_rocky_health_global()
        _redact_for_public(rocky_health)
        http_status = status.HTTP_200_OK if rocky_health.healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(rocky_health.model_dump(), status=http_status)


def get_bytes_health() -> ServiceHealth:
    try:
        bytes_health = get_bytes_client("").health()  # For the health endpoint the organization has no effect
    except HTTPError:
        logger.exception("Error while retrieving Bytes health state")
        bytes_health = ServiceHealth(
            service="bytes", healthy=False, additional="Could not connect to Bytes. Service is possibly down"
        )
    return bytes_health


def _get_octopoes_health(probe: Callable[[], ServiceHealth]) -> ServiceHealth:
    """Call an Octopoes connector health method and convert errors to unhealthy."""
    try:
        return ServiceHealth.model_validate(probe().model_dump())
    except (HTTPError, ConnectorException, ValidationError):
        logger.exception("Error while retrieving Octopoes health state")
        return ServiceHealth(
            service="octopoes", healthy=False, additional="Could not connect to Octopoes. Service is possibly down"
        )


def get_octopoes_health(octopoes_api_connector: OctopoesAPIConnector) -> ServiceHealth:
    return _get_octopoes_health(octopoes_api_connector.health)


def get_octopoes_root_health() -> ServiceHealth:
    """Probe Octopoes reachability via /health — thin verdict, no per-org XTDB probe (#4231).

    Does not check per-organization XTDB health: an installation with hundreds of
    orgs would otherwise drive hundreds of XTDB probes per request. The global
    health page explains this thin verdict to operators.
    """
    connector = OctopoesAPIConnector(settings.OCTOPOES_API, "", timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT)
    health = _get_octopoes_health(connector.root_health)
    if health.healthy:
        health.additional = "Reachability check only — does not probe per-organization XTDB health."
    return health


def get_scheduler_health(organization_code: str | None = None) -> ServiceHealth:
    try:
        scheduler_health = scheduler_client(organization_code).health()
    except SchedulerError:
        logger.exception("Error while retrieving Scheduler health state")
        scheduler_health = ServiceHealth(
            service="scheduler", healthy=False, additional="Could not connect to Scheduler. Service is possibly down"
        )
    return scheduler_health


def _aggregate(services: list[ServiceHealth]) -> ServiceHealth:
    services_healthy = all(service.healthy for service in services)
    additional = None
    if not services_healthy:
        additional = "Rocky will not function properly. Not all services are healthy."
    return ServiceHealth(
        service="rocky", healthy=services_healthy, version=__version__, results=services, additional=additional
    )


def get_rocky_health(organization_code: str, octopoes_api_connector: OctopoesAPIConnector) -> ServiceHealth:
    return _aggregate(
        [
            get_octopoes_health(octopoes_api_connector),
            get_katalogus_health(),
            get_scheduler_health(organization_code),
            get_bytes_health(),
        ]
    )


def get_rocky_health_global() -> ServiceHealth:
    return _aggregate([get_octopoes_root_health(), get_katalogus_health(), get_scheduler_health(), get_bytes_health()])


def _redact_for_public(health_: ServiceHealth) -> None:
    """Public endpoint: keep service + healthy, drop everything that fingerprints (#4231)."""
    health_.version = None
    for sub_result in health_.results:
        sub_result.version = None
        sub_result.additional = None
        sub_result.results = []


def flatten_health(health_: ServiceHealth) -> list[ServiceHealth]:
    results = [health_]
    for sub_result in health_.results:
        results.extend(flatten_health(sub_result))
    health_.results = []
    return results


class GlobalHealthChecks(UserPassesTestMixin, TemplateView):
    """Non-org-scoped human-readable health page (#4231).

    Restricted to superusers, matching the documented access policy for the
    health page (see docs/source/installation-and-deployment/debugging-troubleshooting.rst).
    """

    template_name = "health.html"

    def test_func(self) -> bool:
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("global_health"), "text": _("Health")},
            {"url": reverse("global_health_beautified"), "text": _("Beautified")},
        ]
        rocky_health = get_rocky_health_global()
        context["health_checks"] = flatten_health(rocky_health)
        return context


class HealthChecks(OrganizationView, TemplateView):
    template_name = "health.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"url": reverse("health", kwargs={"organization_code": self.organization.code}), "text": _("Health")},
            {
                "url": reverse("health_beautified", kwargs={"organization_code": self.organization.code}),
                "text": _("Beautified"),
            },
        ]

        rocky_health = get_rocky_health(self.organization.code, self.octopoes_api_connector)
        context["health_checks"] = flatten_health(rocky_health)

        return context
