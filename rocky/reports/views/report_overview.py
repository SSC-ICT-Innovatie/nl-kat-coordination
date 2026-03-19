from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from account.mixins import OrganizationPermissionRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from httpx import HTTPStatusError
from pydantic import TypeAdapter, ValidationError
from tools.ooi_helpers import create_ooi

from octopoes.models import OOI, Reference
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.reports import AssetReport, BaseReport, HydratedReport, Report, ReportRecipe
from reports.views.base import ReportBreadcrumbs, get_selection
from rocky.paginator import RockyPaginator
from rocky.views.mixins import OctopoesView, ReportList
from rocky.views.scheduler import SchedulerView

logger = structlog.get_logger(__name__)


class BreadcrumbsReportOverviewView(ReportBreadcrumbs):
    def build_breadcrumbs(self):
        breadcrumbs = super().build_breadcrumbs()
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)
        breadcrumbs += [{"url": reverse("subreports", kwargs=kwargs) + selection, "text": _("Asset reports")}]
        return breadcrumbs


class ScheduledReportsView(BreadcrumbsReportOverviewView, SchedulerView, ListView):
    """
    Shows all the reports that have ever been generated for the organization.
    """

    paginate_by = 20
    context_object_name = "reports"
    paginator = RockyPaginator
    template_name = "report_overview/scheduled_reports.html"
    task_type = "report"
    context_object_name = "scheduled_reports"

    def get_recipe_ooi(self, recipe_id: str) -> ReportRecipe | None:
        try:
            return self.octopoes_api_connector.get(
                Reference.from_str(f"ReportRecipe|{recipe_id}"), valid_time=self.observed_at
            )
        except (HTTPStatusError, ObjectNotFoundException):
            return None

    def get_reports(self, recipe_id: str) -> list[HydratedReport]:
        try:
            return self.octopoes_api_connector.list_reports(
                valid_time=self.observed_at, recipe_id=UUID(recipe_id)
            ).items
        except (HTTPStatusError, ObjectNotFoundException):
            return []

    def get_queryset(self) -> list[dict[str, Any]]:
        report_schedules = self.get_report_schedules()
        if not report_schedules:
            return []

        recipes = []
        for schedule in report_schedules:
            if not schedule["data"]:
                continue

            recipe_id = schedule["data"]["report_recipe_id"]
            report_recipe = self.get_recipe_ooi(recipe_id)
            reports = self.get_reports(recipe_id)
            schedule_datetime = schedule["deadline_at"]
            total_oois = len(
                {
                    input_ooi.input_ooi if isinstance(input_ooi, AssetReport) else input_ooi
                    for report in reports
                    for input_ooi in report.input_oois
                }
            )

            recipes.append(
                {
                    "schedule_id": schedule["id"],
                    "enabled": schedule["enabled"],
                    "recipe": report_recipe,
                    "cron": schedule["schedule"],
                    "deadline_at": (
                        datetime.strptime(schedule_datetime[0:19] + schedule_datetime[-1:], "%Y-%m-%dT%H:%M:%SZ")
                        if schedule_datetime
                        else "asap"
                    ),
                    "reports": reports,
                    "total_oois": total_oois,
                }
            )

        return recipes

    def post(self, request, *args, **kwargs):
        """Delete report recipe"""
        recipe_id = request.POST.get("recipe_id")

        filters = {"filters": [{"column": "data", "field": "report_recipe_id", "operator": "==", "value": recipe_id}]}
        schedule = self.get_schedule_with_filters(filters) if recipe_id else None

        if not self.organization_member.has_perm("tools.can_delete_oois"):
            messages.error(self.request, _("Not enough permissions"))
            return self.get(request, *args, **kwargs)

        if schedule:
            self.delete_report_schedule(str(schedule.id))
            try:
                self.octopoes_api_connector.delete(
                    Reference.from_str(f"ReportRecipe|{recipe_id}"), valid_time=datetime.now(timezone.utc)
                )
                logger.info(
                    "Schedule and ReportRecipe deleted", event_code="0800083", schedule_id=schedule.id, recipe=recipe_id
                )
                messages.success(self.request, _("Recipe '{}' deleted successfully").format(recipe_id))
            except ObjectNotFoundException:
                messages.error(self.request, _("Recipe not found."))

        else:
            messages.error(self.request, _("No schedule or recipe selected"))

        return redirect(reverse("scheduled_reports", kwargs={"organization_code": self.organization.code}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_report_schedules"] = len(self.object_list)
        context["asset_reports_enabled"] = settings.ASSET_REPORTS
        return context


class ScheduledReportsEnableDisableView(
    OrganizationPermissionRequiredMixin, BreadcrumbsReportOverviewView, SchedulerView, ListView
):
    """
    Enable/disable the schedule for the selected ReportRecipe.
    """

    task_type = "report"
    template_name = "report_overview/scheduled_reports.html"
    permission_required = "tools.can_enable_disable_schedule"

    def get_queryset(self) -> ReportList:
        return ReportList(self.octopoes_api_connector, valid_time=self.observed_at)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        recipe_id = request.POST.get("recipe_id")
        report_name_format = request.POST.get("report_name_format")

        filters = {"filters": [{"column": "data", "field": "report_recipe_id", "operator": "==", "value": recipe_id}]}
        schedule = self.get_schedule_with_filters(filters) if recipe_id else None

        if schedule:
            is_schedule_enabled = not schedule.enabled

            self.edit_report_schedule(str(schedule.id), {"enabled": is_schedule_enabled})

            if is_schedule_enabled:
                messages.success(
                    self.request,
                    _(
                        "Schedule disabled successfully. '{}' will not be generated "
                        "automatically until the schedule is enabled again."
                    ).format(report_name_format),
                )
            else:
                messages.success(
                    self.request,
                    _("Schedule enabled successfully. '{}' will be generated according to schedule.").format(
                        report_name_format
                    ),
                )

        return redirect(reverse("scheduled_reports", kwargs={"organization_code": self.organization.code}))


class ReportHistoryView(BreadcrumbsReportOverviewView, SchedulerView, OctopoesView, ListView):
    """
    Shows all the reports that have ever been generated for the organization.
    """

    paginate_by = 30
    context_object_name = "reports"
    paginator = RockyPaginator
    template_name = "report_overview/report_history.html"
    task_type = "report"

    def post(self, request, *args, **kwargs):
        try:
            self.run_bulk_actions()
        except (ObjectNotFoundException, ValidationError):
            messages.error(request, _("An unexpected error occurred, please check logs for more info."))

        dashboard = self.request.POST.get("dashboard")
        if dashboard:
            return redirect(
                reverse(
                    "organization_crisis_room", kwargs={"organization_code": self.organization.code, "id": dashboard}
                )
            )
        return self.get(request, *args, **kwargs)

    def get_queryset(self) -> ReportList:
        return ReportList(self.octopoes_api_connector, valid_time=self.observed_at)

    def get_report_ooi(self, ooi_pk: str) -> HydratedReport:
        return self.octopoes_api_connector.get_report(ooi_pk, valid_time=self.observed_at)

    def run_bulk_actions(self) -> None:
        action = self.request.POST.get("action", "")
        report_references = self.request.POST.getlist("report_reference", [])

        if action == "rename":
            return self.rename_reports(report_references)

        if action == "delete":
            return self.delete_reports(report_references)

        if action == "rerun":
            return self.rerun_reports(report_references)

    def delete_reports(self, report_references: list[Reference]) -> None:
        if not self.organization_member.has_perm("tools.can_delete_oois"):
            messages.error(self.request, _("Not enough permissions"))
            return

        for report_reference in report_references:
            if not issubclass(Reference.from_str(report_reference).class_type, BaseReport):
                messages.error(self.request, _("Other OOI type selected than Report"))
                return

        self.octopoes_api_connector.delete_many(report_references, datetime.now(timezone.utc))
        logger.info("Reports deleted", event_code=800073, reports=report_references)
        messages.success(self.request, _("Deletion successful."))

    def rerun_reports(self, report_references: list[str]) -> None:
        not_updated_reports = []
        for report_id in report_references:
            report_ooi = self.get_report_ooi(report_id)

            if report_ooi.report_type == "multi-organization-report":
                return messages.warning(
                    self.request,
                    _(
                        "Multi organization reports cannot be rescheduled. "
                        "It consists of imported data from different organizations "
                        "and is not based on newly generated data."
                    ),
                )
            else:
                updated_all = self.rerun_report(report_ooi)

                if updated_all:
                    for asset_report in report_ooi.input_oois:
                        if isinstance(asset_report, AssetReport) and not self.rerun_report(asset_report):
                            updated_all = False
                if not updated_all:
                    not_updated_reports.append(report_ooi.name)
        if not not_updated_reports:
            messages.success(
                self.request, _("Rerun successful. It may take a moment before the new report has been generated.")
            )
        else:
            messages.warning(
                self.request,
                _("Couldn't rerun %s, since the recipe for this report has been disabled or deleted.")
                % ", ".join(not_updated_reports),
            )

    def get_input_data(self, report_ooi: Report) -> dict[str, Any]:
        self.bytes_client.login()

        report_data = TypeAdapter(Any, config={"arbitrary_types_allowed": True}).validate_json(
            self.bytes_client.get_raw(raw_id=report_ooi.data_raw_id)
        )

        return {
            "input_data": {
                "input_oois": report_data["input_data"]["input_oois"],
                "report_types": report_data["input_data"]["report_types"],
                "plugins": report_data["input_data"]["plugins"],
            }
        }

    def get_input_oois(self, ooi_pks: list[str]) -> list[OOI]:
        return [
            self.octopoes_api_connector.get(Reference.from_str(ooi), valid_time=self.observed_at) for ooi in ooi_pks
        ]

    def rerun_report(self, report_ooi: Report | AssetReport) -> bool:
        """Rerun an existing Report and its AssetReports."""
        deadline_at = datetime.now(timezone.utc).isoformat()
        report_recipe_id = str(report_ooi.report_recipe.tokenized.recipe_id)
        filters = {
            "filters": [{"column": "data", "field": "report_recipe_id", "operator": "==", "value": report_recipe_id}]
        }
        schedule = self.get_schedule_with_filters(filters)
        if schedule and schedule.enabled:
            self.scheduler_client.patch_schedule(schedule_id=str(schedule.id), params={"deadline_at": deadline_at})
            return True
        return False

    def rename_reports(self, report_references: list[str]) -> None:
        report_names = self.request.POST.getlist("report_name", [])
        error_reports = []

        if not report_references or not report_names:
            messages.error(self.request, _("Renaming failed. Empty report name found."))

        if len(report_references) != len(report_names):
            messages.error(self.request, _("Report names and reports does not match."))

        for index, report_id in enumerate(report_references):
            report_ooi = self.get_report_ooi(report_id).to_report()
            report_ooi.name = report_names[index]
            try:
                create_ooi(self.octopoes_api_connector, self.bytes_client, report_ooi, datetime.now(timezone.utc))
            except ValidationError:
                error_reports.append(f'"{report_ooi.name}"')

        if not error_reports:
            logger.info("Reports created", event_code=800071, reports=report_references)
            return messages.success(self.request, _("Reports successfully renamed."))

        return messages.error(self.request, _("Report {} could not be renamed.").format(", ".join(error_reports)))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_reports"] = len(self.object_list)
        context["selected_reports"] = self.request.GET.getlist("report", [])
        context["asset_reports_enabled"] = settings.ASSET_REPORTS
        return context


class SubreportView(BreadcrumbsReportOverviewView, OctopoesView, ListView):
    """
    Shows all the subreports that belong to the selected parent report.
    """

    paginate_by = 150
    breadcrumbs_step = 2
    context_object_name = "asset_reports"
    paginator = RockyPaginator
    template_name = "report_overview/subreports.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.report_id = self.request.GET.get("report_id")

    def get_queryset(self) -> ReportList:
        return ReportList(self.octopoes_api_connector, valid_time=self.observed_at, report_id=self.report_id)

    def get_report_ooi(self, ooi_pk: str) -> HydratedReport:
        return self.octopoes_api_connector.get_report(ooi_pk, valid_time=self.observed_at)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_oois"] = len(self.object_list)
        context["report_ooi"] = self.get_report_ooi(self.report_id).to_report()
        return context
