from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from tools.view_helpers import Breadcrumb

from reports.report_types.multi_organization_report.report import MultiOrganizationReport
from reports.views.base import (
    OOISelectionView,
    ReportBreadcrumbs,
    ReportFinalSettingsView,
    ReportPluginView,
    ReportTypeSelectionView,
    SaveReportView,
    get_selection,
)
from reports.views.mixins import SaveMultiReportMixin
from reports.views.view_helpers import MultiReportStepsMixin


class BreadcrumbsMultiReportView(ReportBreadcrumbs):
    def build_breadcrumbs(self) -> list[Breadcrumb]:
        breadcrumbs = super().build_breadcrumbs()
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)
        breadcrumbs += [
            {"url": reverse("multi_report_landing", kwargs=kwargs) + selection, "text": _("Multi report")},
            {"url": reverse("multi_report_select_oois", kwargs=kwargs) + selection, "text": _("Select objects")},
            {
                "url": reverse("multi_report_select_report_types", kwargs=kwargs) + selection,
                "text": _("Select report types"),
            },
            {"url": reverse("multi_report_setup_scan", kwargs=kwargs) + selection, "text": _("Configuration")},
            {"url": reverse("multi_report_export_setup", kwargs=kwargs) + selection, "text": _("Export setup")},
            {"url": reverse("multi_report_view", kwargs=kwargs) + selection, "text": _("View report")},
        ]
        return breadcrumbs


class LandingMultiReportView(BreadcrumbsMultiReportView):
    """
    Landing page to start the 'Multi Report' flow.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect(reverse("multi_report_select_oois", kwargs=self.get_kwargs()))


class OOISelectionMultiReportView(MultiReportStepsMixin, BreadcrumbsMultiReportView, OOISelectionView):
    """
    Select OOIs for the 'Multi Report' flow.
    """

    template_name = "generate_report/select_oois.html"
    breadcrumbs_step = 3
    current_step = 1
    report_type = MultiOrganizationReport


class ReportTypesSelectionMultiReportView(
    MultiReportStepsMixin, BreadcrumbsMultiReportView, ReportTypeSelectionView, TemplateView
):
    """
    Shows all possible report types from a list of OOIs.
    Chooses report types for the 'Multi Report' flow.
    """

    template_name = "generate_report/select_report_types.html"
    breadcrumbs_step = 4
    current_step = 2
    report_type = MultiOrganizationReport


class SetupScanMultiReportView(MultiReportStepsMixin, BreadcrumbsMultiReportView, ReportPluginView):
    """
    Show required and optional plugins to start scans to multi OOIs to include in report.
    """

    template_name = "generate_report/setup_scan.html"
    breadcrumbs_step = 5
    current_step = 3
    report_type = MultiOrganizationReport


class ExportSetupMultiReportView(MultiReportStepsMixin, BreadcrumbsMultiReportView, ReportFinalSettingsView):
    """
    Shows the export setup page where users can set their export preferences.
    """

    template_name = "generate_report/export_setup.html"
    breadcrumbs_step = 6
    current_step = 4
    report_type = MultiOrganizationReport


class MultiReportView(SaveMultiReportMixin, BreadcrumbsMultiReportView, SaveReportView):
    """
    Shows the multi report from OOIS and report types.
    """

    template_name = "multi_report.html"
    breadcrumbs_step = 6
    current_step = 5
    report_type = MultiOrganizationReport
