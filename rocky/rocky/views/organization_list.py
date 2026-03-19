import logging
from datetime import datetime

from account.models import KATUser
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from structlog import get_logger
from tools.models import Organization
from tools.view_helpers import OrganizationBreadcrumbsMixin

from octopoes.connector.octopoes import OctopoesAPIConnector

logger = get_logger(__name__)


class OrganizationListView(OrganizationBreadcrumbsMixin, ListView):
    template_name = "organizations/organization_list.html"

    def get_queryset(self) -> QuerySet[Organization]:
        user: KATUser = self.request.user
        return (
            Organization.objects.annotate(member_count=Count("members"))
            .prefetch_related("tags")
            .filter(id__in=[organization.id for organization in user.organizations])
            .order_by("name")
        )

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Perform actions based on action type"""
        if request.POST.get("action") == "recalculate":
            if not self.request.user.has_perm("tools.can_recalculate_bits"):
                raise PermissionDenied()
            organizations = self.request.user.organizations
            number_of_bits = 0
            failed = []
            start_time = datetime.now()
            for organization in organizations:
                try:
                    logger.info("Recalculating bits", event_code=920000, organization_code=organization.code)
                    number_of_bits += OctopoesAPIConnector(
                        settings.OCTOPOES_API, organization.code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
                    ).recalculate_bits()
                except Exception as exc:
                    failed.append(f"{organization}, ({str(exc)})")
                    logging.warning("Failed recalculating bits for %s, %s", organization, exc)
            duration = datetime.now() - start_time
            n_failed = len(failed)
            message = f"Recalculated {number_of_bits} bits for {len(organizations)-n_failed} organizations."
            message += f" Duration: {duration}."
            if failed:
                message += f"\nFailed for {n_failed} organisations: {', '.join(failed)}"
            messages.add_message(request, messages.INFO, _(message))
            return self.get(request, *args, **kwargs)
        else:
            raise HttpResponseBadRequest("Unknown action")
