import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from operator import attrgetter
from typing import Any, Literal, cast
from uuid import uuid4

import structlog
from account.mixins import OrganizationView
from crisis_room.forms import AddReportSectionDashboardItemForm
from django.conf import settings
from django.contrib import messages
from django.forms import Form
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView
from django_weasyprint import WeasyTemplateResponseMixin
from katalogus.client import Boefje, KATalogus, KATalogusError, Plugin
from tools.ooi_helpers import create_ooi
from tools.view_helpers import Breadcrumb, BreadcrumbsMixin, PostRedirect, url_with_querystring

from octopoes.models import OOI, Reference
from octopoes.models.ooi.reports import AssetReport, ReportRecipe
from octopoes.models.ooi.reports import BaseReport as ReportOOI
from octopoes.models.types import OOIType, type_by_name
from reports.forms import OOITypeMultiCheckboxForReportForm, ReportScheduleStartDateForm
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.concatenated_report.report import ConcatenatedReport
from reports.report_types.definitions import AggregateReport, BaseReport, Report, report_plugins_union
from reports.report_types.helpers import (
    get_ooi_types_from_aggregate_report,
    get_ooi_types_with_report,
    get_report_by_id,
    get_report_types_for_ooi_types,
    get_report_types_for_oois,
    get_report_types_from_aggregate_report,
)
from reports.report_types.multi_organization_report.report import MultiOrganizationReport
from reports.utils import JSONEncoder, debug_json_keys
from rocky.views.mixins import AddDashboardItemFormMixin, ObservedAtMixin, OOIList
from rocky.views.ooi_view import BaseOOIListView, OOIFilterView
from rocky.views.scheduler import SchedulerView

REPORTS_PRE_SELECTION = {"clearance_level": ["2", "3", "4"], "clearance_type": "declared"}


def get_selection(request: HttpRequest, pre_selection: Mapping[str, str | Sequence[str]] | None = None) -> str:
    if pre_selection is not None:
        return "?" + urlencode(pre_selection, True)
    return "?" + urlencode(request.GET, True)


logger = structlog.get_logger(__name__)


class ReportBreadcrumbs(OrganizationView, BreadcrumbsMixin):
    breadcrumbs_step: int = 1

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.breadcrumbs = self.build_breadcrumbs()

    def get_kwargs(self):
        return {"organization_code": self.organization.code}

    def is_valid_breadcrumbs(self):
        return self.breadcrumbs_step < len(self.breadcrumbs)

    def build_breadcrumbs(self) -> list[Breadcrumb]:
        kwargs = self.get_kwargs()
        selection = get_selection(self.request)

        return [{"url": reverse("reports", kwargs=kwargs) + selection, "text": _("Reports")}]

    def get_breadcrumbs(self):
        if self.is_valid_breadcrumbs():
            return self.breadcrumbs[: self.breadcrumbs_step]
        return self.breadcrumbs

    def get_current(self):
        return self.breadcrumbs[self.breadcrumbs_step - 1]["url"]

    def get_previous(self):
        if self.is_valid_breadcrumbs() and self.breadcrumbs_step >= 2:
            return self.breadcrumbs[self.breadcrumbs_step - 2]["url"]
        return self.get_current()

    def get_next(self):
        if self.is_valid_breadcrumbs():
            return self.breadcrumbs[self.breadcrumbs_step]["url"]
        return self.get_current()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = self.get_breadcrumbs()
        context["next"] = self.get_next()
        context["previous"] = self.get_previous()
        return context


class ReportsLandingView(ReportBreadcrumbs, TemplateView):
    """
    Landing page for Reports.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect(reverse("report_history", kwargs=self.get_kwargs()))


def hydrate_plugins(report_types: list[type["BaseReport"]], katalogus: KATalogus) -> dict[str, list[Plugin]]:
    plugins: dict[str, list[Plugin]] = {"required": [], "optional": []}
    merged_plugins = report_plugins_union(report_types)

    required_plugins_ids = list(merged_plugins["required"])
    optional_plugins_ids = list(merged_plugins["optional"])

    # avoid empty list getting all plugins from KATalogus
    if required_plugins_ids:
        plugins["required"] = sorted(katalogus.get_plugins(ids=required_plugins_ids), key=attrgetter("name"))
    if optional_plugins_ids:
        plugins["optional"] = sorted(katalogus.get_plugins(ids=optional_plugins_ids), key=attrgetter("name"))

    return plugins


def format_plugin_data(report_type_plugins: dict[str, list[Plugin]]):
    return [
        {
            "required": required_optional == "required",
            "enabled": plugin.enabled,
            "name": plugin.name,
            "scan_level": plugin.scan_level.value if isinstance(plugin, Boefje) else 0,
            "type": plugin.type,
            "description": plugin.description,
        }
        for required_optional, plugins in report_type_plugins.items()
        for plugin in plugins
    ]


class BaseReportView(OOIFilterView, ReportBreadcrumbs):
    """
    This view is the base for the report creation wizard.
    All the necessary functions and variables needed.
    """

    NONE_OOI_SELECTION_MESSAGE = _("Select at least one OOI to proceed.")
    NONE_REPORT_TYPE_SELECTION_MESSAGE = _("Select at least one report type to proceed.")

    report_type: type[BaseReport] | None = None  # Get report types from a specific report type ex. AggregateReport

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.selected_oois = self.get_ooi_pks()
        self.selected_report_types = self.get_report_type_ids()

    def get_ooi_selection(self) -> list[str]:
        return sorted(set(self.request.POST.getlist("ooi", [])))

    def all_oois_selected(self) -> bool:
        return "all" in self.request.GET.getlist("ooi", [])

    def get_ooi_pks(self) -> list[str]:
        if self.all_oois_selected():
            return sorted([ooi.primary_key for ooi in self.get_oois()])
        return self.get_ooi_selection()

    def get_total_oois(self):
        return len(self.selected_oois)

    def get_report_ooi_types(self):
        if self.report_type == AggregateOrganisationReport:
            return get_ooi_types_from_aggregate_report(AggregateOrganisationReport)
        if self.report_type == MultiOrganizationReport:
            return MultiOrganizationReport.input_ooi_types
        return get_ooi_types_with_report()

    def get_ooi_types(self):
        ooi_types = self.get_report_ooi_types()
        if self.filtered_ooi_types:
            return {type_by_name(t) for t in self.filtered_ooi_types if type_by_name(t) in ooi_types}
        return ooi_types

    def get_oois(self) -> list[OOI]:
        if self.all_oois_selected():
            return self.octopoes_api_connector.list_objects(
                self.get_ooi_types(),
                valid_time=self.observed_at,
                limit=OOIList.HARD_LIMIT,
                scan_level=self.get_ooi_scan_levels(),
                scan_profile_type=self.get_ooi_profile_types(),
            ).items

        return list(
            self.octopoes_api_connector.load_objects_bulk(
                {Reference.from_str(x) for x in self.get_ooi_selection()}, self.observed_at
            ).values()
        )

    def get_ooi_filter_forms(self) -> dict[str, Form]:
        return {
            "ooi_type_form": OOITypeMultiCheckboxForReportForm(
                sorted([ooi_class.get_ooi_type() for ooi_class in self.get_report_ooi_types()]), self.request.GET
            )
        }

    def get_report_type_ids(self) -> list[str]:
        return sorted(set(self.request.POST.getlist("report_type", [])))

    def get_report_types(self) -> list[type[BaseReport]]:
        return [get_report_by_id(report_type_id) for report_type_id in self.selected_report_types]

    @staticmethod
    def get_report_types_from_ooi_selelection(
        report_types: set[type[BaseReport]] | set[type[Report]] | set[type[MultiOrganizationReport]],
    ) -> list[dict[str, str]]:
        """
        The report types are fetched from which ooi is selected. Shows all report types for the oois.
        """

        return [
            {
                "id": report_type.id,
                "name": report_type.name,
                "description": report_type.description,
                "label_style": report_type.label_style,
            }
            for report_type in report_types
        ]

    def get_report_types_for_generate_report(self):
        object_selection = self.request.POST.get("object_selection", "")
        if object_selection == "query":
            report_types = get_report_types_for_ooi_types(self.get_ooi_types())
        else:
            report_types = get_report_types_for_oois(self.selected_oois)
        return self.get_report_types_from_ooi_selelection(report_types)

    def get_report_types_for_aggregate_report(self) -> dict[str, list[dict[str, str]]]:
        reports_dict = get_report_types_from_aggregate_report(AggregateOrganisationReport)
        report_types: dict[str, list[dict[str, str]]] = {}

        for option, reports in reports_dict.items():
            report_types[option] = self.get_report_types_from_ooi_selelection(reports)
        return report_types

    def get_available_report_types(self) -> tuple[list[dict[str, str]] | dict[str, list[dict[str, str]]], int]:
        report_types: list[dict[str, str]] | dict[str, list[dict[str, str]]] = {}

        if self.report_type == AggregateOrganisationReport:
            report_types = self.get_report_types_for_aggregate_report()
            return report_types, len(
                [report_type for report_type_list in report_types.values() for report_type in report_type_list]
            )

        elif self.report_type == MultiOrganizationReport:
            report_types = self.get_report_types_from_ooi_selelection({MultiOrganizationReport})
            return report_types, len(report_types)

        report_types = self.get_report_types_for_generate_report()
        return report_types, len(report_types)

    def get_observed_at(self):
        return self.observed_at if self.observed_at < datetime.now(timezone.utc) else datetime.now(timezone.utc)

    def is_single_report(self) -> bool:
        return len(self.get_report_type_ids()) == 1

    def get_input_recipe(self):
        object_selection = self.request.POST.get("object_selection", "")
        query = {}

        if object_selection == "query":
            query = {
                "ooi_types": [t.__name__ for t in self.get_ooi_types()],
                "scan_level": self.get_ooi_scan_levels(),
                "scan_type": self.get_ooi_profile_types(),
                "search_string": self.search_string,
                "order_by": self.order_by,
                "asc_desc": self.sorting_order,
            }

        if not query:
            return {"input_oois": self.get_ooi_pks()}

        return {"query": query}

    def create_report_recipe(
        self, report_name_format: str, report_type: str | None, schedule: str | None
    ) -> ReportRecipe:
        report_recipe = ReportRecipe(
            user_id=self.request.user.id,
            recipe_id=uuid4(),
            report_name_format=report_name_format,
            input_recipe=self.get_input_recipe(),
            report_type=report_type,
            asset_report_types=self.get_report_type_ids(),
            cron_expression=schedule,
        )
        create_ooi(
            api_connector=self.octopoes_api_connector,
            bytes_client=self.bytes_client,
            ooi=report_recipe,
            observed_at=datetime.now(timezone.utc),
        )
        logger.info("ReportRecipe created", event_code=800091, report_recipe=report_recipe)
        return report_recipe

    def get_input_data(self) -> dict[str, Any]:
        return {
            "input_data": {
                "input_oois": self.get_ooi_pks(),
                "report_types": self.get_report_type_ids(),
                "plugins": report_plugins_union(self.get_report_types()),
            }
        }

    def get_initial_report_name(self) -> str:
        return "${report_type} for ${oois_count} objects"

    def get_parent_report_type(self):
        if self.report_type is not None:
            return self.report_type.id
        return ConcatenatedReport.id

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["all_oois_selected"] = self.all_oois_selected()
        context["selected_oois"] = self.selected_oois
        context["selected_report_types"] = self.selected_report_types
        context["is_single_report"] = self.is_single_report()
        context["object_selection"] = self.request.POST.get("object_selection", "")

        return context


class OOISelectionView(BaseReportView, BaseOOIListView):
    """
    Shows a list of OOIs to select from and handles OOIs selection requests.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        object_selection = request.GET.get("object_selection", "")

        if object_selection == "query":
            return PostRedirect(self.get_next())

    def post(self, request, *args, **kwargs):
        if not (self.get_ooi_selection() or self.all_oois_selected()):
            messages.error(request, self.NONE_OOI_SELECTION_MESSAGE)
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_ooi_filter_forms())
        return context


class ReportTypeSelectionView(BaseReportView, TemplateView):
    """
    Shows report types and handles selections and requests.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object_selection = request.POST.get("object_selection", "")
        self.available_report_types, self.counted_report_types = self.get_available_report_types()

    def post(self, request, *args, **kwargs):
        if not (self.get_ooi_selection() or self.all_oois_selected()) and self.object_selection != "query":
            return PostRedirect(self.get_previous())
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["oois"] = self.get_oois()  # show listed oois in report type view.
        context["total_oois"] = self.get_total_oois()  # adds counter to the heading

        context["available_report_types"] = self.available_report_types  # shows tiles of report types

        context["count_available_report_types"] = self.counted_report_types  # counter next to heading
        # especially for the CSS selector to set toggle on.
        context["all_report_types_checked"] = len(self.get_report_type_ids()) == self.counted_report_types

        return context

    def all_oois_selected(self) -> bool:
        return "all" in self.request.POST.getlist("ooi", [])


class ReportPluginView(BaseReportView, TemplateView):
    """
    This view shows the required and optional plugins together with the summary per report type.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.plugins = None

        try:
            self.plugins = hydrate_plugins(self.get_report_types(), self.get_katalogus())
        except KATalogusError as error:
            messages.error(self.request, error.message)

    def post(self, request, *args, **kwargs):
        if self.plugins is None:
            return PostRedirect(self.get_previous())

        all_plugins_enabled = self.all_plugins_enabled()

        if not self.get_report_type_ids():
            messages.error(request, self.NONE_REPORT_TYPE_SELECTION_MESSAGE)
            return PostRedirect(self.get_previous())

        if "return" in self.request.POST and all_plugins_enabled:
            return PostRedirect(self.get_previous())

        if all_plugins_enabled:
            return PostRedirect(self.get_next())
        return self.get(request, *args, **kwargs)

    def all_plugins_enabled(self) -> bool:
        return all(self.plugins_enabled().values())

    def plugins_enabled(self) -> dict[str, bool]:
        if self.plugins is not None:
            return {
                "required": all([plugin.enabled for plugin in self.plugins["required"]]),
                "optional": all([plugin.enabled for plugin in self.plugins["optional"]]),
            }

        return {"required": False, "optional": False}

    def get_plugins_data(self):
        report_types: dict[str, Any] = {}
        plugin_report_types: dict[str, list] = {}
        total_enabled_plugins = {"required": 0, "optional": 0}
        total_available_plugins = {"required": 0, "optional": 0}

        if self.plugins is not None:
            for report_type in self.get_report_types():
                for plugin_type in ["required", "optional"]:
                    # Mypy doesn't infer this automatically https://github.com/python/mypy/issues/9168
                    plugin_type = cast(Literal["required", "optional"], plugin_type)
                    number_of_enabled = sum(
                        (1 if plugin.enabled and plugin.id in report_type.plugins[plugin_type] else 0)
                        for plugin in self.plugins[plugin_type]
                    )
                    report_plugins = report_type.plugins[plugin_type]

                    for plugin in report_plugins:
                        if plugin not in plugin_report_types:
                            plugin_report_types[plugin] = [
                                {"name": report_type.name, "label_style": report_type.label_style}
                            ]
                        else:
                            plugin_report_types[plugin].append(
                                {"name": report_type.name, "label_style": report_type.label_style}
                            )

                    total_enabled_plugins[plugin_type] += number_of_enabled
                    total_available_plugins[plugin_type] += len(report_plugins)

                    if report_type.name not in report_types:
                        report_types[report_type.name] = {}

                    report_types[report_type.name][f"number_of_enabled_{plugin_type}"] = number_of_enabled
                    report_types[report_type.name][f"number_of_available_{plugin_type}"] = len(report_plugins)

            plugin_data = {
                "total_enabled_plugins": total_enabled_plugins,
                "total_available_plugins": total_available_plugins,
                "report_types": report_types,
                "plugin_report_types": plugin_report_types,
            }

            return plugin_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enabled_plugins"] = self.plugins_enabled()
        context["plugin_data"] = self.get_plugins_data()
        context["plugins"] = self.plugins
        return context


class ReportFinalSettingsView(BaseReportView, SchedulerView, TemplateView):
    report_type: type[BaseReport] | None = None
    task_type = "report"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.get_report_type_ids():
            messages.error(request, self.NONE_REPORT_TYPE_SELECTION_MESSAGE)
            return PostRedirect(self.get_previous())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_schedule_form_start_date"] = self.get_report_schedule_form_start_date_time_recurrence()
        context["report_name_form"] = self.get_report_name_form()
        return context


class SaveReportView(BaseReportView, SchedulerView, FormView):
    task_type = "report"
    form_class = ReportScheduleStartDateForm

    def form_invalid(self, form):
        """
        We need to overwrite this as FormView renders invalid forms with a get request,
        we need to adapt it using Postredirect, returning invalid form.
        """

        return PostRedirect(self.get_current())

    def form_valid(self, form):
        start_datetime = form.cleaned_data["start_datetime"]
        recurrence = form.cleaned_data["recurrence"]

        schedule = (
            self.convert_recurrence_to_cron_expressions(recurrence, start_datetime)
            if recurrence is not None and recurrence != "once"
            else None
        )

        report_type = self.get_parent_report_type()

        report_name_format = self.request.POST.get("report_name", "Report")

        report_recipe = self.create_report_recipe(report_name_format, report_type, schedule)

        self.create_report_schedule(report_recipe, start_datetime)

        return redirect(reverse("scheduled_reports", kwargs={"organization_code": self.organization.code}))


class ViewReportView(ObservedAtMixin, OrganizationView, TemplateView, AddDashboardItemFormMixin):
    """
    This will display reports using report_id from reports history.
    Will fetch Report OOI and recreate report with data saved in bytes.
    """

    add_dashboard_item_form = AddReportSectionDashboardItemForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        self.report_ooi = self.get_report_ooi()
        self.report_data, self.input_oois, self.report_types, self.plugins = self.get_report_data()
        self.recipe_ooi = self.get_recipe_ooi(self.report_ooi.report_recipe)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.add_to_dashboard()

    def get(self, request, *args, **kwargs):
        if "json" in self.request.GET and self.request.GET["json"] == "true":
            response = {
                "organization_code": self.organization.code,
                "organization_name": self.organization.name,
                "organization_tags": list(self.organization.tags.all()),
                "data": self.report_data,
            }

            try:
                response = JsonResponse(response, encoder=JSONEncoder)
            except TypeError:
                # We can't use translated strings as keys in JSON. This
                # debugging code makes it easy to spot where the problem is.
                if settings.DEBUG:
                    debug_json_keys(self.report_data, [])
                raise
            else:
                response["Content-Disposition"] = f"attachment; filename=report-{self.organization.code}.json"
                return response

        return super().get(request, *args, **kwargs)

    @property
    def custom_observed_at(self):
        return (
            self.observed_at.replace(hour=23, minute=59, second=59, microsecond=999999)
            if self.observed_at < datetime.now(timezone.utc)
            else datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)
        )

    def get_report_ooi(self) -> ReportOOI:
        if "asset_report_id" in self.request.GET:
            ooi_pk = self.request.GET.get("asset_report_id")
            return self.octopoes_api_connector.get(Reference.from_str(ooi_pk), valid_time=self.custom_observed_at)

        return self.octopoes_api_connector.get_report(
            Reference.from_str(self.request.GET.get("report_id")), valid_time=self.custom_observed_at
        )

    def get_recipe_ooi(self, recipe_id: str) -> ReportRecipe | None:
        return self.octopoes_api_connector.get(Reference.from_str(recipe_id), valid_time=self.observed_at)

    def get_template_names(self):
        if self.report_ooi.report_type and issubclass(get_report_by_id(self.report_ooi.report_type), AggregateReport):
            return ["aggregate_report.html"]
        if self.report_ooi.report_type and issubclass(
            get_report_by_id(self.report_ooi.report_type), MultiOrganizationReport
        ):
            return ["multi_report.html"]
        return ["generate_report.html"]

    def get_asset_reports(self) -> list[AssetReport]:
        return [
            report
            for report in self.octopoes_api_connector.get_report(self.report_ooi.reference, self.observed_at).input_oois
            if isinstance(report, AssetReport)
        ]

    def get_input_oois(self, ooi_pks: list[str]) -> list[OOIType]:
        return list(
            self.octopoes_api_connector.load_objects_bulk(
                {Reference.from_str(ooi) for ooi in ooi_pks}, valid_time=self.observed_at
            ).values()
        )

    def get_plugins(self, plugins_dict: dict[str, list[str]]) -> list[dict[str, list[Plugin]]]:
        plugins: dict[str, list[Plugin]] = {"required": [], "optional": []}

        plugin_ids_required = plugins_dict["required"]
        plugin_ids_optional = plugins_dict["optional"]

        katalogus_plugins = self.get_katalogus().get_plugins(ids=plugin_ids_required + plugin_ids_optional)
        for plugin in katalogus_plugins:
            if plugin.id in plugin_ids_required:
                plugins["required"].append(plugin)
            if plugin.id in plugin_ids_optional:
                plugins["optional"].append(plugin)

        plugins["required"] = sorted(plugins["required"], key=attrgetter("enabled"))
        plugins["optional"] = sorted(plugins["optional"], key=attrgetter("enabled"), reverse=True)

        return format_plugin_data(plugins)

    def get_report_types(self, report_type_ids: Iterable[str]) -> list[dict[str, str]]:
        report_types = []
        for report_type_id in report_type_ids:
            report_type = get_report_by_id(report_type_id)
            report_types.append(
                {
                    "name": report_type.name,
                    "label_style": report_type.label_style,
                    "description": report_type.description,
                }
            )
        return report_types

    def get_report_data_from_bytes(self, reports: list[ReportOOI]) -> list[tuple[str, dict[str, Any]]]:
        self.bytes_client.login()

        bytes_datas = self.bytes_client.get_raws(
            self.organization.code, raw_ids=[report.data_raw_id for report in reports]
        )
        return [(x[0], json.loads(x[1])) for x in bytes_datas]

    def get_report_data_single_report(
        self,
    ) -> tuple[
        dict[str, dict[str, dict[str, Any]]], list[AssetReport], list[dict[str, Any]], list[dict[str, list[Plugin]]]
    ]:
        report_data: dict[str, Any] = self.get_report_data_from_bytes([self.report_ooi])[0][1]

        report_types = self.get_report_types(report_data["input_data"]["report_types"])
        plugins = self.get_plugins(report_data["input_data"]["plugins"])
        oois = self.get_input_oois(report_data["input_data"]["input_oois"])

        report_data[self.report_ooi.report_type] = {}

        for ooi in oois:
            report_data[self.report_ooi.report_type][ooi.primary_key] = {
                "data": report_data["report_data"],
                "template": self.report_ooi.template,
                "report_name": self.report_ooi.name,
            } | report_data["input_data"]

        return report_data, oois, report_types, plugins

    def get_report_data_aggregate_report_or_multi_report(
        self,
    ) -> tuple[
        dict[str, dict[str, dict[str, Any]]], list[AssetReport], list[dict[str, Any]], list[dict[str, list[Plugin]]]
    ]:
        report_data = self.get_report_data_from_bytes([self.report_ooi])[0][1]
        report_types = self.get_report_types(report_data["input_data"]["report_types"])
        plugins = self.get_plugins(report_data["input_data"]["plugins"])
        if settings.ASSET_REPORTS:
            oois = self.get_input_oois(list({asset_ooi.input_ooi for asset_ooi in self.report_ooi.input_oois}))
        else:
            oois = self.get_input_oois(list({input_ooi for input_ooi in self.report_ooi.input_oois}))

        return report_data, oois, report_types, plugins

    def get_report_data_concatenated_report(
        self,
    ) -> tuple[
        dict[str, dict[str, dict[str, Any]]], list[AssetReport], list[dict[str, Any]], list[dict[str, list[Plugin]]]
    ]:
        report_data: dict[str, dict[str, dict[str, Any]]] = {}

        asset_reports = self.get_asset_reports()
        bytes_datas = {key: value for key, value in self.get_report_data_from_bytes(asset_reports)}

        ooi_pks = set()

        for report in asset_reports:
            ooi_pks.add(report.input_ooi)
            bytes_data = bytes_datas[report.data_raw_id]
            report_data.setdefault(report.report_type, {})[report.input_ooi] = {
                "data": bytes_data["report_data"],
                "template": report.template,
                "report_name": report.name,
            } | bytes_data["input_data"]
        oois = self.get_input_oois(list(ooi_pks))
        report_type_ids = {child_report.report_type for child_report in asset_reports}
        report_types = self.get_report_types(report_type_ids)
        plugins = self.get_plugins(self.get_report_data_from_bytes([self.report_ooi])[0][1]["input_data"]["plugins"])

        return report_data, oois, report_types, plugins

    def get_report_data(self):
        if issubclass(get_report_by_id(self.report_ooi.report_type), ConcatenatedReport):
            return self.get_report_data_concatenated_report()
        if issubclass(get_report_by_id(self.report_ooi.report_type), AggregateReport | MultiOrganizationReport):
            return self.get_report_data_aggregate_report_or_multi_report()

        return self.get_report_data_single_report()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_data"] = self.report_data
        context["report_ooi"] = self.report_ooi
        context["recipe_ooi"] = self.recipe_ooi
        context["oois"] = self.input_oois
        context["report_types"] = self.report_types
        context["plugins"] = self.plugins
        context["report_download_json_url"] = url_with_querystring(
            reverse("view_report", kwargs={"organization_code": self.organization.code}),
            True,
            **dict(json="true", **self.request.GET),
        )
        context["report_download_pdf_url"] = url_with_querystring(
            reverse("view_report_pdf", kwargs={"organization_code": self.organization.code}), True, **self.request.GET
        )

        return context


class ViewReportPDFView(ViewReportView, WeasyTemplateResponseMixin):
    pdf_filename = "report.pdf"
    pdf_attachment = False
    pdf_options = {"pdf_variant": "pdf/ua-1"}

    def get_template_names(self):
        if self.report_ooi.report_type and issubclass(get_report_by_id(self.report_ooi.report_type), AggregateReport):
            return ["aggregate_report_pdf.html"]
        if self.report_ooi.report_type and issubclass(
            get_report_by_id(self.report_ooi.report_type), MultiOrganizationReport
        ):
            return ["multi_report_pdf.html"]
        return ["generate_report_pdf.html"]
