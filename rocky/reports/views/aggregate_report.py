from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from httpx import HTTPError
from tools.view_helpers import Breadcrumb, PostRedirect

from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.views.base import (
    REPORTS_PRE_SELECTION,
    OOISelectionView,
    ReportBreadcrumbs,
    ReportFinalSettingsView,
    ReportPluginView,
    ReportTypeSelectionView,
    SaveReportView,
    get_selection,
)
from reports.views.mixins import SaveAggregateReportMixin
from reports.views.view_helpers import AggregateReportStepsMixin


class BreadcrumbsAggregateReportView(ReportBreadcrumbs):
    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)
        breadcrumbs += [
            {"url": reverse("aggregate_report_landing", kwargs=kwargs) + selection, "text": _("Aggregate report")},
            {"url": reverse("aggregate_report_select_oois", kwargs=kwargs) + selection, "text": _("Select objects")},
            {
                "url": reverse("aggregate_report_select_report_types", kwargs=kwargs) + selection,
                "text": _("Select report types"),
            },
            {"url": reverse("aggregate_report_setup_scan", kwargs=kwargs) + selection, "text": _("Configuration")},
            {"url": reverse("aggregate_report_export_setup", kwargs=kwargs) + selection, "text": _("Export setup")},
            {"url": reverse("aggregate_report_save", kwargs=kwargs) + selection, "text": _("Save report")},
        ]
        return breadcrumbs


class LandingAggregateReportView(BreadcrumbsAggregateReportView):
    """
    Landing page to start the 'Aggregate Report' flow.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect(
            reverse("aggregate_report_select_oois", kwargs=self.get_kwargs())
            + get_selection(request, REPORTS_PRE_SELECTION)
        )


class OOISelectionAggregateReportView(AggregateReportStepsMixin, BreadcrumbsAggregateReportView, OOISelectionView):
    """
    Select Objects for the 'Aggregate Report' flow.
    """

    template_name = "generate_report/select_oois.html"
    breadcrumbs_step = 3
    current_step = 1
    report_type = AggregateOrganisationReport

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["channel"] = "aggregate_report"
        return context


class ReportTypesSelectionAggregateReportView(
    AggregateReportStepsMixin, BreadcrumbsAggregateReportView, ReportTypeSelectionView, TemplateView
):
    """
    Shows all possible report types from a list of Objects.
    Chooses report types for the 'Aggregate Report' flow.
    """

    template_name = "generate_report/select_report_types.html"
    breadcrumbs_step = 4
    current_step = 2
    report_type = AggregateOrganisationReport


class SetupScanAggregateReportView(
    SaveAggregateReportMixin, AggregateReportStepsMixin, BreadcrumbsAggregateReportView, ReportPluginView
):
    """
    Show required and optional plugins to start scans to generate OOIs to include in report.
    """

    template_name = "generate_report/setup_scan.html"
    breadcrumbs_step = 5
    current_step = 3
    report_type = AggregateOrganisationReport


class ExportSetupAggregateReportView(
    AggregateReportStepsMixin, BreadcrumbsAggregateReportView, ReportFinalSettingsView
):
    """
    Shows the export setup page where users can set their export preferences.
    """

    template_name = "generate_report/export_setup.html"
    breadcrumbs_step = 6
    current_step = 4
    report_type = AggregateOrganisationReport

    def post(self, request, *args, **kwargs):
        selected_plugins = request.POST.getlist("plugin", [])

        if not selected_plugins:
            return super().post(request, *args, **kwargs)

        if not self.organization_member.has_perm("tools.can_enable_disable_boefje"):
            messages.error(request, _("You do not have the required permissions to enable plugins."))
            return PostRedirect(self.get_previous())

        for selected_plugin in selected_plugins:
            try:
                self.katalogus_client.enable_boefje_by_id(selected_plugin)
            except HTTPError:
                messages.error(
                    request,
                    _("An error occurred while enabling {}. The plugin is not available.").format(selected_plugin),
                )
                return self.post(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)


class SaveAggregateReportView(SaveAggregateReportMixin, BreadcrumbsAggregateReportView, SaveReportView):
    """
    Save the report and redirect to the saved report
    """

    template_name = "aggregate_report.html"
    breadcrumbs_step = 6
    current_step = 5
    report_type = AggregateOrganisationReport
