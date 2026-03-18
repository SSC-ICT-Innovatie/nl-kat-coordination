import json
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any
from uuid import UUID

import structlog
from account.mixins import OrganizationView
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models.manager import BaseManager
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from httpx import HTTPStatusError, ReadTimeout
from pydantic import Field
from reports.report_types.findings_report.report import SEVERITY_OPTIONS
from tools.forms.ooi_form import _EXCLUDED_OOI_TYPES
from tools.models import Organization, OrganizationMember

from crisis_room.forms import AddDashboardForm
from crisis_room.models import MAX_POSITION, Dashboard, DashboardItem
from octopoes.config.settings import DEFAULT_SCAN_LEVEL_FILTER, DEFAULT_SCAN_PROFILE_TYPE_FILTER
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference, ScanLevel, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.ooi.findings import RiskLevelSeverity
from octopoes.models.ooi.reports import HydratedReport
from octopoes.models.types import get_collapsed_types, type_by_name
from rocky.bytes_client import get_bytes_client
from rocky.views.mixins import FindingList

logger = structlog.get_logger(__name__)


@dataclass
class DashboardItemView:
    item: DashboardItem | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class DashboardService:
    @staticmethod
    def get_organizations_findings(report_data: dict[str, Any]) -> dict[str, Any]:
        findings = {}
        highest_risk_level = ""
        if "findings" in report_data and report_data["findings"] and report_data["findings"]["finding_types"]:
            finding_types = report_data["findings"]["finding_types"]
            highest_risk_level = finding_types[0]["finding_type"]["risk_severity"]
            critical_high_finding_types = list(
                filter(
                    lambda finding_type: finding_type["finding_type"]["risk_severity"] == "critical"
                    or finding_type["finding_type"]["risk_severity"] == "high",
                    finding_types,
                )
            )
            report_data["findings"]["finding_types"] = critical_high_finding_types[:25]

        findings = report_data | {"highest_risk_level": highest_risk_level}
        return findings

    def get_reports(self, valid_time: datetime, report_filters: list[tuple[str, str]]) -> dict[UUID, HydratedReport]:
        """
        Returns for each recipe ID query'ed, the latest (valid_time) HydratedReport.
        """

        if report_filters:
            org_code, _ = report_filters[0]
            # We need at least 1 org connector to fetch reports from all other orgs.
            connector = OctopoesAPIConnector(
                settings.OCTOPOES_API, org_code, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
            )
            try:
                return connector.bulk_list_reports(valid_time, report_filters)
            except (HTTPStatusError, ObjectNotFoundException, ReadTimeout) as error:
                logger.error("An error occurred: %s", error)
                return {}
        return {}

    @staticmethod
    def get_report_bytes_data(raw_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Return for each raw id key its bytes content value across all member organizations.
        """
        # When organization is None, data is fetched across all organizations.
        bytes_client = get_bytes_client(None)
        bytes_client.login()
        try:
            return bytes_client.get_raws_all(raw_ids)
        except (HTTPStatusError, ObjectNotFoundException, ReadTimeout) as error:
            logger.error("An error occurred: %s", error)
            return {}

    def get_dashboard_items(self, dashboard_items: BaseManager[DashboardItem]) -> list[DashboardItemView]:
        dashboard_items_with_data: list[DashboardItemView] = []

        recipes_data = {}
        reports_data = {}

        raw_ids = []
        report_filters = []

        # First collect al data, if recipe id is found then fetch recipe ids to get reports later.
        for dashboard_item in dashboard_items:
            if not dashboard_item.recipe and dashboard_item.source == "object_list":
                item_data = DashboardItemView(dashboard_item, self.get_ooi_list(dashboard_item))
                dashboard_items_with_data.append(item_data)
            elif not dashboard_item.recipe and dashboard_item.source == "finding_list":
                item_data = DashboardItemView(dashboard_item, self.get_finding_list(dashboard_item))
                dashboard_items_with_data.append(item_data)
            elif dashboard_item.recipe:
                report_filters.append((dashboard_item.dashboard.organization.code, str(dashboard_item.recipe)))
                recipes_data[dashboard_item] = dashboard_item.recipe

        if recipes_data:
            # Returns for each recipe id, its Hydrated report.
            reports: dict[UUID, HydratedReport] = self.get_reports(datetime.now(timezone.utc), report_filters)

            # After reports are collected, collect data raw ids to fetch data from Bytes later.
            for dashboard_item, recipe_id in recipes_data.items():
                try:
                    if (
                        dashboard_item.findings_dashboard or not dashboard_item.source
                    ):  # Report section from aggregate report
                        hydrated_report = reports[recipe_id]
                    else:  # Report section from a normal report
                        octopoes_client = OctopoesAPIConnector(
                            settings.OCTOPOES_API,
                            dashboard_item.dashboard.organization.code,
                            timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT,
                        )
                        hydrated_report = octopoes_client.get(
                            Reference.from_str(dashboard_item.source), datetime.now(timezone.utc)
                        )
                    raw_ids.append(hydrated_report.data_raw_id)
                    reports_data[dashboard_item] = hydrated_report
                except KeyError:
                    continue

            # Get report data from bytes, per data raw id its report data
            report_data_from_bytes: dict[str, dict[str, Any]] = self.get_report_bytes_data(raw_ids)

            # Finally merge all data necessary and create dashboard items to show on the dashboard.
            for dashboard_item, hydrated_report in reports_data.items():
                item_data = DashboardItemView(dashboard_item, {"report": hydrated_report})
                octopoes_client = OctopoesAPIConnector(
                    settings.OCTOPOES_API,
                    dashboard_item.dashboard.organization.code,
                    timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT,
                )

                try:
                    report_data = report_data_from_bytes[hydrated_report.data_raw_id]

                    if dashboard_item.findings_dashboard:
                        report_data = self.get_organizations_findings(report_data)

                    report = item_data.data["report"]

                    if dashboard_item.recipe and dashboard_item.source:
                        parent_report_id = hydrated_report.report_recipe.replace("ReportRecipe", "Report")
                        parent_report = octopoes_client.get_report(parent_report_id, report.observed_at)
                        item_data.data.update(
                            {"parent_report": {"primary_key": parent_report.primary_key, "name": parent_report.name}}
                        )
                    recipe = octopoes_client.get(report.report_recipe, report.observed_at)
                    item_data.data.update({"report_data": report_data, "recipe": recipe})
                    dashboard_items_with_data.append(item_data)
                except KeyError:
                    continue

        return dashboard_items_with_data

    @staticmethod
    def get_organizations_findings_summary(organizations_findings: list[DashboardItemView]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "total_by_severity_per_finding_type": {severity: 0 for severity in SEVERITY_OPTIONS},
            "total_by_severity": {severity: 0 for severity in SEVERITY_OPTIONS},
            "total_finding_types": 0,
            "total_occurrences": 0,
        }

        summary_added = False

        for findings in organizations_findings:
            if "findings" in findings.data["report_data"] and "summary" in findings.data["report_data"]["findings"]:
                for summary_item, data in findings.data["report_data"]["findings"]["summary"].items():
                    if isinstance(data, dict):
                        for severity, total in data.items():
                            summary[summary_item][severity] += total
                            summary_added = True
                    else:
                        summary[summary_item] += data
                        summary_added = True

        if not summary_added:
            return {}

        return summary

    def get_ooi_list(self, dashboard_item) -> dict[str, Any]:
        query = json.loads(dashboard_item.query)
        ooi_list = []

        all_oois = {
            ooi_class for ooi_class in get_collapsed_types() if ooi_class.get_ooi_type() not in _EXCLUDED_OOI_TYPES
        }
        all_scan_levels = DEFAULT_SCAN_LEVEL_FILTER
        all_scan_profile_types = DEFAULT_SCAN_PROFILE_TYPE_FILTER

        ooi_types = (
            {type_by_name(t) for t in query["ooi_type"] if t not in _EXCLUDED_OOI_TYPES}
            if query["ooi_type"]
            else all_oois
        )
        scan_level = (
            {ScanLevel(int(cl)) for cl in query["clearance_level"]} if query["clearance_level"] else all_scan_levels
        )
        scan_profile_type = (
            {ScanProfileType(ct) for ct in query["clearance_type"]}
            if query["clearance_type"]
            else all_scan_profile_types
        )

        octopoes_client = OctopoesAPIConnector(
            settings.OCTOPOES_API,
            dashboard_item.dashboard.organization.code,
            timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT,
        )

        observed_at = (
            datetime.strptime(query["observed_at"], "%Y-%m-%d") if query["observed_at"] else datetime.now(timezone.utc)
        )
        # for now we check till end of day
        valid_time = datetime.combine(observed_at.date(), time(23, 59, 59), tzinfo=timezone.utc)

        ooi_list = octopoes_client.list_objects(
            ooi_types,
            valid_time=valid_time,
            limit=query["limit"],
            scan_level=scan_level,
            scan_profile_type=scan_profile_type,
            search_string=query["search"],
            order_by=query["order_by"],
            asc_desc=query["sorting_order"],
        ).items

        return {"object_list": ooi_list}

    def get_finding_list(self, dashboard_item) -> dict[str, Any]:
        query = json.loads(dashboard_item.query)
        finding_list = []

        severities = set()
        for severity in query["severity"]:
            try:
                severities.add(RiskLevelSeverity(severity))
            except ValueError as e:
                messages.error(e)

        octopoes_client = OctopoesAPIConnector(
            settings.OCTOPOES_API,
            dashboard_item.dashboard.organization.code,
            timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT,
        )

        limit = query["limit"]

        muted_findings = query["muted_findings"]
        exclude_muted = muted_findings == "non-muted"
        only_muted = muted_findings == "muted"

        observed_at = (
            datetime.strptime(query["observed_at"], "%Y-%m-%d") if query["observed_at"] else datetime.now(timezone.utc)
        )
        # for now we check till end of day
        valid_time = datetime.combine(observed_at.date(), time(23, 59, 59), tzinfo=timezone.utc)

        finding_list = FindingList(
            octopoes_connector=octopoes_client,
            valid_time=valid_time,
            severities=severities,
            exclude_muted=exclude_muted,
            only_muted=only_muted,
            search_string=query["search"],
            order_by=query["order_by"],
            asc_desc=query["sorting_order"],
        )[:limit]

        return {"finding_list": finding_list}


class CrisisRoomView(TemplateView):
    """This is the Crisis Room for all organizations."""

    template_name = "crisis_room.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)

        dashboard_service = DashboardService()
        organizations = self.get_user_organizations()

        dashboard_items = DashboardItem.objects.filter(
            dashboard__organization__in=organizations, findings_dashboard=True
        )

        self.organizations_findings = dashboard_service.get_dashboard_items(dashboard_items)
        self.organizations_findings_summary = dashboard_service.get_organizations_findings_summary(
            self.organizations_findings
        )

    def get_user_organizations(self) -> list[Organization]:
        return [member.organization for member in OrganizationMember.objects.filter(user=self.request.user)]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"url": reverse("crisis_room"), "text": "Crisis room"}]
        context["dashboard_items"] = self.organizations_findings
        context["organizations_findings_summary"] = self.organizations_findings_summary
        return context


class OrganizationsCrisisRoomLandingView(OrganizationView, TemplateView):
    template_name = "organization_crisis_room.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        default_dashboard = Dashboard.objects.filter(organization=self.organization).first()
        if default_dashboard:
            return redirect(
                reverse(
                    "organization_crisis_room",
                    kwargs={"organization_code": self.organization.code, "id": default_dashboard.id},
                )
            )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["add_dashboard_form"] = AddDashboardForm
        return context


class OrganizationsCrisisRoomView(OrganizationView, TemplateView):
    """This is the Crisis Room for a single organization."""

    template_name = "organization_crisis_room.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.dashboard_service = DashboardService()
        dashboard_id = kwargs["id"]

        try:
            self.dashboard = Dashboard.objects.get(id=dashboard_id, organization=self.organization)
            dashboard_items = DashboardItem.objects.filter(dashboard=self.dashboard).order_by("position")
            items = sorted(
                self.dashboard_service.get_dashboard_items(dashboard_items),
                key=lambda x: x.item.position if x.item else MAX_POSITION + 1,
            )
            self.dashboard_items: list[DashboardItemView] | None = items

        except Dashboard.DoesNotExist:
            messages.error(request, "Dashboard does not exist.")
            self.dashboard = None
            self.dashboard_items = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboards"] = Dashboard.objects.filter(organization=self.organization)
        context["dashboard"] = self.dashboard
        context["dashboard_items"] = self.dashboard_items
        context["add_dashboard_form"] = AddDashboardForm
        context["breadcrumbs"] = [
            {
                "url": reverse(
                    "organization_crisis_room_landing", kwargs={"organization_code": self.organization.code}
                ),
                "text": "Crisis room",
            }
        ]
        return context


class DeleteDashboardView(OrganizationView):
    """Delete the selected dashboard."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        dashboard_name = request.POST.get("dashboard_name")
        dashboard_id = request.POST.get("dashboard_id")

        if not self.organization_member.can_delete_dashboard:
            raise PermissionDenied()

        try:
            dashboard = Dashboard.objects.get(id=dashboard_id, organization=self.organization)
        except Dashboard.DoesNotExist:
            messages.error(request, f"Dashboard '{dashboard_name}' not found.")
            return redirect(
                reverse("organization_crisis_room_landing", kwargs={"organization_code": self.organization.code})
            )

        deleted, _ = dashboard.delete()

        if deleted >= 1:
            messages.success(request, f"Dashboard '{dashboard_name}' has been deleted.")
        else:
            messages.error(request, f"Dashboard '{dashboard_name}' could not be deleted.")

        return redirect(
            reverse("organization_crisis_room_landing", kwargs={"organization_code": self.organization.code})
        )


class DeleteDashboardItemView(OrganizationView):
    """Delete the selected dashboard item."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        dashboard_item_name = request.POST.get("dashboard_item_name")
        dashboard_item_id = request.POST.get("dashboard_item_id")

        if not self.organization_member.can_delete_dashboard_item:
            raise PermissionDenied()

        try:
            dashboard_item = DashboardItem.objects.get(
                id=dashboard_item_id, dashboard__organization=self.organization, name=dashboard_item_name
            )
        except DashboardItem.DoesNotExist:
            messages.error(request, f"Dashboard item '{dashboard_item_name}' not found.")
            return redirect(
                reverse("organization_crisis_room_landing", kwargs={"organization_code": self.organization.code})
            )

        dashboard_item_name = dashboard_item.name
        dashboard_id = dashboard_item.dashboard.id

        deleted, _ = dashboard_item.delete()

        if deleted >= 1:
            messages.success(request, f"Dashboard item '{dashboard_item_name}' has been deleted.")
            logger.info(event_code=900309)
        else:
            messages.error(request, f"Dashboard item '{dashboard_item_name}' could not be deleted.")

        return redirect(
            reverse(
                "organization_crisis_room", kwargs={"organization_code": self.organization.code, "id": dashboard_id}
            )
        )


class UpdateDashboardItemView(OrganizationView):
    """Update the selected dashboard item, change the position up or down."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        dashboard_item_id = request.POST.get("dashboard_item")
        dashboard_id = request.POST.get("dashboard")
        update_position = request.POST.get("move")

        if not self.organization_member.can_reposition_dashboard_item:
            raise PermissionDenied()

        try:
            dashboard_item = DashboardItem.objects.get(id=dashboard_item_id, dashboard__organization=self.organization)
            dashboard_item.update_position(update_position)

            return redirect(
                reverse(
                    "organization_crisis_room",
                    kwargs={"organization_code": self.organization.code, "id": dashboard_item.dashboard.id},
                )
                + "#dashboard-item-"
                + slugify(dashboard_item.name)
            )
        except DashboardItem.DoesNotExist:
            messages.error(request, "Dashboard item not found.")
        return redirect(
            reverse(
                "organization_crisis_room", kwargs={"organization_code": self.organization.code, "id": dashboard_id}
            )
        )


class AddDashboardView(OrganizationView, FormView):
    """Add a new dashboard tab to the organization."""

    template_name = "organization_crisis_room.html"
    form_class = AddDashboardForm

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Create a new dashboard tab."""

        if not self.organization_member.can_add_dashboard:
            raise PermissionDenied()

        form = self.get_form()
        if form.is_valid():
            dashboard_name = request.POST.get("dashboard_name")
            try:
                dashboard, created = Dashboard.objects.get_or_create(
                    name=dashboard_name, organization=self.organization
                )

                if created:
                    messages.success(request, f"Dashboard '{dashboard.name}' has been created.")
                else:
                    messages.error(request, f"Dashboard with name '{dashboard.name}' already exists.")

                return redirect(
                    reverse(
                        "organization_crisis_room",
                        kwargs={"organization_code": self.organization.code, "id": dashboard.id},
                    )
                )
            except IntegrityError:
                messages.error(request, "Dashboard could not be created.")

            return redirect(
                reverse("organization_crisis_room_landing", kwargs={"organization_code": self.organization.code})
            )
        else:
            return redirect(
                reverse("organization_crisis_room_landing", kwargs={"organization_code": self.organization.code})
            )
