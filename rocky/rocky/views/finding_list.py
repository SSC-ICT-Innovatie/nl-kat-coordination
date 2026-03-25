from collections.abc import Iterable
from enum import Enum
from typing import Any, Literal

import structlog
from crisis_room.forms import AddFindingListDashboardItemForm
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.urls.base import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from tools.forms.findings import (
    FindingSearchForm,
    FindingSeverityMultiSelectForm,
    MutedFindingSelectionForm,
    OrderByFindingTypeForm,
    OrderBySeverityForm,
)
from tools.view_helpers import Breadcrumb, BreadcrumbsMixin

from octopoes.models.ooi.findings import RiskLevelSeverity
from rocky.paginator import RockyPaginator
from rocky.views.mixins import (
    FINDING_LIST_COLUMNS,
    AddDashboardItemFormMixin,
    FindingList,
    OctopoesView,
    SeveritiesMixin,
)

logger = structlog.get_logger(__name__)


def sort_by_severity_desc(findings: Iterable) -> list[dict[str, Any]]:
    # Sorting is stable (when multiple records have the same key, their original
    # order is preserved) so if we first sort by finding id the findings with
    # the same risk score will be sorted by finding id
    sorted_by_finding_id = sorted(findings, key=lambda x: x["finding_type"].id)
    sorted_findings = sorted(sorted_by_finding_id, key=lambda x: x["risk_level_score"], reverse=True)
    for index, finding in enumerate(sorted_findings, start=1):
        finding["finding_number"] = index
    return sorted_findings


def generate_findings_metadata(
    findings: FindingList, severity_filter: Iterable[RiskLevelSeverity] | None = None
) -> list[dict[str, Any]]:
    findings_meta = []

    for finding in findings[: FindingList.HARD_LIMIT]:
        finding_type = finding.finding_type

        if not severity_filter or (finding_type.risk_severity and finding_type.risk_severity in severity_filter):
            findings_meta.append(
                {
                    "finding_number": 0,
                    "finding": finding,
                    "finding_type": finding_type,
                    "severity": finding_type.risk_severity.name if finding_type.risk_severity else "",
                    "risk_level_score": finding_type.risk_score,
                }
            )

    return sort_by_severity_desc(findings_meta)


class PageActions(Enum):
    ADD_TO_DASHBOARD = "add_to_dashboard"


class FindingListFilter(OctopoesView, SeveritiesMixin, ListView):
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.severities = self.get_severities()
        self.muted_findings = request.GET.get("muted_findings", "non-muted")

        self.exclude_muted = self.muted_findings == "non-muted"
        self.only_muted = self.muted_findings == "muted"

        self.search_string = request.GET.get("search", "")

    @property
    def count_active_filters(self):
        return (
            len(self.severities)
            + (1 if self.muted_findings else 0)
            + self.count_observed_at_filter()
            + (1 if self.search_string else 0)
        )

    def get_queryset(self) -> FindingList:
        return FindingList(self.octopoes_api_connector, **self.get_queryset_params())

    def get_queryset_params(self):
        return {
            "valid_time": self.observed_at,
            "severities": self.severities,
            "exclude_muted": self.exclude_muted,
            "only_muted": self.only_muted,
            "search_string": self.search_string,
            "order_by": self.order_by,
            "asc_desc": self.sorting_order,
        }

    @property
    def order_by(self) -> Literal["score", "finding_type"]:
        return "finding_type" if self.request.GET.get("order_by", "") == "finding_type" else "score"

    @property
    def sorting_order(self) -> Literal["asc", "desc"]:
        return "asc" if self.request.GET.get("sorting_order", "") == "asc" else "desc"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["severity_filter"] = FindingSeverityMultiSelectForm(self.request.GET)
        context["muted_findings_filter"] = MutedFindingSelectionForm(self.request.GET)
        context["table_columns"] = FINDING_LIST_COLUMNS
        context["finding_search_form"] = FindingSearchForm(self.request.GET)
        context["active_filters_counter"] = self.count_active_filters
        context["order_by"] = self.order_by
        context["order_by_severity_form"] = OrderBySeverityForm(self.request.GET)
        context["order_by_finding_type_form"] = OrderByFindingTypeForm(self.request.GET)
        context["sorting_order"] = self.sorting_order
        context["sorting_order_class"] = "ascending" if self.sorting_order == "asc" else "descending"
        context["severities"] = self.severities
        context["exclude_muted"] = self.exclude_muted
        context["only_muted"] = self.only_muted
        context["search_string"] = self.search_string
        return context


class FindingListView(BreadcrumbsMixin, FindingListFilter, AddDashboardItemFormMixin):
    template_name = "findings/finding_list.html"
    paginate_by = 150
    add_dashboard_item_form = AddFindingListDashboardItemForm
    paginator_class = RockyPaginator

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        return [
            {
                "url": reverse_lazy("finding_list", kwargs={"organization_code": self.organization.code}),
                "text": _("Findings"),
            }
        ]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Perform bulk action on selected oois."""
        action = request.POST.get("action")

        if action == PageActions.ADD_TO_DASHBOARD.value:
            return self.add_to_dashboard()

        messages.add_message(request, messages.ERROR, _("Unknown action."))
        return self.get(request, status=404, *args, **kwargs)
