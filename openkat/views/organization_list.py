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

        order_by = self.request.GET.get("order_by", "name")
        sorting_order = self.request.GET.get("sorting_order", "asc")

        if order_by and sorting_order == "desc":
            return queryset.order_by(f"-{order_by}")

        return queryset.order_by(order_by)

    def get_context_data(self, **kwargs):
        # Ensure context from all mixins is properly merged
        context = super().get_context_data(**kwargs)
        context["order_by"] = self.request.GET.get("order_by")
        context["sorting_order"] = self.request.GET.get("sorting_order", "asc")
        context["sorting_order_class"] = "ascending" if context["sorting_order"] == "asc" else "descending"
        context["columns"] = [
            {"field": "name", "label": "Name", "sortable": True},
            {"field": "tags", "label": "Tags", "sortable": False},
            {"field": "settings", "label": "Settings", "sortable": False},
        ]

        return context
