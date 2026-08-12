from typing import Any

import structlog
from account.mixins import OrganizationView
from django.http import HttpRequest, JsonResponse
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from httpx import HTTPError
from katalogus.health import get_katalogus_health

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


def get_bytes_health() -> ServiceHealth:
    try:
        bytes_health = get_bytes_client("").health()  # For the health endpoint the organization has no effect
    except HTTPError:
        logger.exception("Error while retrieving Bytes health state")
        bytes_health = ServiceHealth(
            service="bytes", healthy=False, additional="Could not connect to Bytes. Service is possibly down"
        )
    return bytes_health


def get_octopoes_health(octopoes_api_connector: OctopoesAPIConnector) -> ServiceHealth:
    try:
        # we need to make sure we're using Rocky's ServiceHealth model, not Octopoes' model
        octopoes_health = ServiceHealth.model_validate(octopoes_api_connector.health().model_dump())
    except HTTPError:
        logger.exception("Error while retrieving Octopoes health state")
        octopoes_health = ServiceHealth(
            service="octopoes", healthy=False, additional="Could not connect to Octopoes. Service is possibly down"
        )
    return octopoes_health


def get_scheduler_health(organization_code: str) -> ServiceHealth:
    try:
        scheduler_health = scheduler_client(organization_code).health()
    except SchedulerError:
        logger.exception("Error while retrieving Scheduler health state")
        scheduler_health = ServiceHealth(
            service="scheduler", healthy=False, additional="Could not connect to Scheduler. Service is possibly down"
        )
    return scheduler_health


def get_rocky_health(organization_code: str, octopoes_api_connector: OctopoesAPIConnector) -> ServiceHealth:
    services = [
        get_octopoes_health(octopoes_api_connector),
        get_katalogus_health(),
        get_scheduler_health(organization_code),
        get_bytes_health(),
    ]

    services_healthy = all(service.healthy for service in services)
    additional = None
    if not services_healthy:
        additional = "Rocky will not function properly. Not all services are healthy."
    rocky_health = ServiceHealth(
        service="rocky", healthy=services_healthy, version=__version__, results=services, additional=additional
    )
    return rocky_health


def flatten_health(health_: ServiceHealth) -> list[ServiceHealth]:
    results = [health_]
    for sub_result in health_.results:
        results.extend(flatten_health(sub_result))
    health_.results = []
    return results


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
