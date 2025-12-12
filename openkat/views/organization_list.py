from django.db.models import Count, QuerySet
from django.views.generic import ListView
from structlog import get_logger

from openkat.mixins import OrganizationFilterMixin
from openkat.models import Organization
from openkat.view_helpers import OrganizationBreadcrumbsMixin

logger = get_logger(__name__)


class OrganizationListView(OrganizationFilterMixin, OrganizationBreadcrumbsMixin, ListView):
    template_name = "organizations/organization_list.html"

    def get_queryset(self) -> QuerySet[Organization]:
        # Start with organizations the user is a member of
        queryset = (
            Organization.objects.annotate(member_count=Count("members"))
            .prefetch_related("tags")
            .filter(id__in=[organization.id for organization in self.request.user.organizations])
        )

        # Filter by organization if provided
        organization_ids = self.request.GET.getlist("organization")
        if organization_ids:
            queryset = queryset.filter(id__in=organization_ids)

        return queryset

    def get_context_data(self, **kwargs):
        # Ensure context from all mixins is properly merged
        context = super().get_context_data(**kwargs)
        return context
