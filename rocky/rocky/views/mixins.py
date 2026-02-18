from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cached_property
from operator import attrgetter
from typing import Literal, TypedDict, cast

import structlog
from account.mixins import OrganizationView
from account.models import KATUser
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django.views.generic.edit import FormMixin
from httpx import HTTPError
from katalogus.client import Boefje
from pydantic import BaseModel
from tools.forms.base import ObservedAtForm
from tools.forms.settings import DEPTH_DEFAULT, DEPTH_MAX
from tools.models import Organization, OrganizationMember
from tools.ooi_helpers import get_knowledge_base_data_for_ooi_store
from tools.view_helpers import convert_date_to_datetime, get_ooi_url

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import OOI, Reference, ScanLevel, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException
from octopoes.models.explanation import InheritanceSection
from octopoes.models.ooi.findings import Finding, FindingType, RiskLevelSeverity
from octopoes.models.ooi.reports import AssetReport, HydratedReport, Report
from octopoes.models.origin import Origin, OriginType
from octopoes.models.tree import ReferenceTree
from octopoes.models.types import get_relations
from rocky.bytes_client import get_bytes_client

logger = structlog.get_logger(__name__)

ORIGIN_MAX_AGE = timedelta(days=2)

FINDING_LIST_COLUMNS = {
    "severity": _("Severity"),
    "finding": _("Finding"),
    "location": _("Location"),
    "tree": _("Tree"),
    "graph": _("Graph"),
}

OBJECT_LIST_COLUMNS = {
    "object": _("Object"),
    "object_type": _("Type"),
    "clearance_level": _("Clearance level"),
    "clearance_type": _("Clearance type"),
}


@dataclass
class HydratedFinding:
    finding: Finding
    ooi: OOI
    finding_type: FindingType


class OriginData(BaseModel):
    origin: Origin
    normalizer: dict | None = None
    boefje: Boefje | None = None
    params: dict[str, str] | None = None

    @property
    def is_old(self) -> bool:
        return self.is_older_than(ORIGIN_MAX_AGE)

    def is_older_than(self, time_delta: timedelta) -> bool:
        if not self.normalizer:
            return False

        if (observation_date := self.normalizer.get("raw_data", {}).get("boefje_meta", {}).get("ended_at")) is None:
            raise ValueError("Observation date is missing in normalizer meta")

        observation_date = observation_date.replace(tzinfo=timezone.utc)

        return observation_date < datetime.now(timezone.utc) - time_delta


class Origins(TypedDict):
    declarations: list[OriginData]
    observations: list[OriginData]
    inferences: list[OriginData]


class OOIAttributeError(AttributeError):
    pass


class ObservedAtMixin:
    request: HttpRequest

    @cached_property
    def observed_at(self) -> datetime:
        observed_at = self.request.GET.get("observed_at", None)
        if not observed_at:
            return datetime.now(timezone.utc)

        try:
            datetime_format = "%Y-%m-%d"
            date_time = convert_date_to_datetime(datetime.strptime(observed_at, datetime_format))
            if date_time.date() > datetime.now(timezone.utc).date():
                messages.warning(self.request, _("The selected date is in the future."))
            return date_time
        except ValueError:
            try:
                ret = datetime.fromisoformat(observed_at)
                if not ret.tzinfo:
                    ret = ret.replace(tzinfo=timezone.utc)

                return ret
            except ValueError:
                messages.error(self.request, _("Can not parse date, falling back to show current date."))
                return datetime.now(timezone.utc)


class OctopoesView(ObservedAtMixin, OrganizationView):
    add_object_to_dashboard_form = None

    def get_single_ooi(self, pk: str) -> OOI:
        try:
            ref = Reference.from_str(pk)
            ooi = self.octopoes_api_connector.get(ref, valid_time=self.observed_at)

            return ooi
        except Exception as e:
            # TODO: raise the exception but let the handling be done by  the method that implements "get_single_ooi"
            self.handle_connector_exception(e)
            raise

    def get_origins(self, reference: Reference, organization: Organization) -> Origins:
        declarations: list[OriginData] = []
        observations: list[OriginData] = []
        inferences: list[OriginData] = []
        results: Origins = {"declarations": declarations, "observations": observations, "inferences": inferences}

        try:
            origins = self.octopoes_api_connector.list_origins(self.observed_at, result=reference)
        except Exception as e:
            logger.error("Could not load origins for OOI: %s from octopoes, error: %s", reference, e)
            return results

        try:
            bytes_client = get_bytes_client(organization.code)
            bytes_client.login()
        except HTTPError as e:
            logger.error(e)
            return results

        katalogus = self.get_katalogus()

        for origin in origins:
            origin = OriginData(origin=origin)
            if origin.origin.origin_type != OriginType.OBSERVATION or not origin.origin.task_id:
                if origin.origin.origin_type == OriginType.DECLARATION:
                    declarations.append(origin)
                elif origin.origin.origin_type == OriginType.INFERENCE:
                    inferences.append(origin)
                continue

            try:
                normalizer_data = bytes_client.get_normalizer_meta(origin.origin.task_id)
            except HTTPError as e:
                logger.error("Could not load Normalizer meta for task_id: %s, error: %s", origin.origin.task_id, e)
            else:
                boefje_meta = normalizer_data["raw_data"]["boefje_meta"]
                boefje_id = boefje_meta["boefje"]["id"]
                if boefje_meta.get("ended_at"):
                    try:
                        boefje_meta["ended_at"] = datetime.strptime(boefje_meta["ended_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:
                        boefje_meta["ended_at"] = datetime.strptime(boefje_meta["ended_at"], "%Y-%m-%dT%H:%M:%SZ")
                origin.normalizer = normalizer_data
                if boefje_id != "manual":
                    try:
                        origin.boefje = katalogus.get_plugin(boefje_id)
                    except HTTPError as e:
                        logger.error("Could not load boefje %s from katalogus: %s", boefje_id, e)
            observations.append(origin)

        return results

    def handle_connector_exception(self, exception: Exception) -> None:
        if isinstance(exception, ObjectNotFoundException):
            raise Http404("OOI not found")

        raise exception

    def get_scan_profile_inheritance(self, ooi: OOI) -> list[InheritanceSection]:
        return self.octopoes_api_connector.get_scan_profile_inheritance(ooi.reference, self.observed_at)


class OOIList:
    HARD_LIMIT = 99_999_999

    def __init__(
        self,
        octopoes_connector: OctopoesAPIConnector,
        ooi_types: set[type[OOI]],
        valid_time: datetime,
        scan_level: set[ScanLevel],
        scan_profile_type: set[ScanProfileType],
        search_string: str | None = None,
        order_by: Literal["scan_level", "object_type"] = "object_type",
        asc_desc: Literal["asc", "desc"] = "asc",
    ):
        self.octopoes_connector = octopoes_connector
        self.ooi_types = ooi_types
        self.valid_time = valid_time
        self.ordered = True
        self._count = 0
        self.scan_level = scan_level
        self.scan_profile_type = scan_profile_type
        self.search_string = search_string
        self.order_by = order_by
        self.asc_desc = asc_desc

    @cached_property
    def count(self) -> int:
        if not self.ooi_types:
            return 0
        return self.octopoes_connector.list_objects(
            self.ooi_types,
            valid_time=self.valid_time,
            limit=0,
            scan_level=self.scan_level,
            scan_profile_type=self.scan_profile_type,
            search_string=self.search_string,
        ).count

    def __len__(self):
        return self.count

    def __getitem__(self, key: int | slice) -> list[OOI]:
        if not self.ooi_types:
            return []
        if isinstance(key, slice):
            offset = key.start or 0
            limit = OOIList.HARD_LIMIT
            if key.stop:
                limit = key.stop - offset

            return self.octopoes_connector.list_objects(
                self.ooi_types,
                valid_time=self.valid_time,
                offset=offset,
                limit=limit,
                scan_level=self.scan_level,
                scan_profile_type=self.scan_profile_type,
                search_string=self.search_string,
                order_by=self.order_by,
                asc_desc=self.asc_desc,
            ).items

        elif isinstance(key, int):
            return self.octopoes_connector.list_objects(
                self.ooi_types,
                valid_time=self.valid_time,
                offset=key,
                limit=1,
                scan_level=self.scan_level,
                scan_profile_type=self.scan_profile_type,
                search_string=self.search_string,
                order_by=self.order_by,
                asc_desc=self.asc_desc,
            ).items


class FindingList:
    HARD_LIMIT = 99_999_999

    def __init__(
        self,
        octopoes_connector: OctopoesAPIConnector,
        valid_time: datetime,
        severities: Iterable[RiskLevelSeverity],
        exclude_muted: bool = True,
        only_muted: bool = False,
        search_string: str | None = None,
        order_by: Literal["score", "finding_type"] = "score",
        asc_desc: Literal["asc", "desc"] = "desc",
    ):
        self.octopoes_connector = octopoes_connector
        self.valid_time = valid_time
        self.ordered = True
        self._count = None
        self.severities = severities
        self.exclude_muted = exclude_muted
        self.only_muted = only_muted
        self.search_string = search_string
        self.order_by = order_by
        self.asc_desc = asc_desc

    @cached_property
    def count(self) -> int:
        return self.octopoes_connector.list_findings(
            severities=self.severities,
            valid_time=self.valid_time,
            exclude_muted=self.exclude_muted,
            only_muted=self.only_muted,
            limit=0,
            search_string=self.search_string,
        ).count

    def __len__(self):
        return self.count

    def __getitem__(self, key: int | slice) -> list[HydratedFinding]:
        if isinstance(key, slice):
            offset = key.start or 0
            limit = self.HARD_LIMIT
            if key.stop:
                limit = key.stop - offset
            findings = self.octopoes_connector.list_findings(
                severities=self.severities,
                valid_time=self.valid_time,
                exclude_muted=self.exclude_muted,
                only_muted=self.only_muted,
                offset=offset,
                limit=limit,
                search_string=self.search_string,
                order_by=self.order_by,
                asc_desc=self.asc_desc,
            ).items
            ooi_references = {finding.ooi for finding in findings}
            finding_type_references = {finding.finding_type for finding in findings}
            objects = self.octopoes_connector.load_objects_bulk(
                ooi_references | finding_type_references, valid_time=self.valid_time
            )

            hydrated_findings = []
            for finding in findings:
                if finding.ooi not in objects or finding.finding_type not in objects:
                    continue
                hydrated_findings.append(
                    HydratedFinding(
                        finding=finding, finding_type=objects[finding.finding_type], ooi=objects[finding.ooi]
                    )
                )
            return hydrated_findings

        raise NotImplementedError("FindingList only supports slicing")


class EnrichedReport:
    report: Report
    asset_reports: list[Report] | None
    total_asset_reports: int
    total_objects: int
    report_type_summary: dict[str, int]
    input_oois: list[str]


class ReportList:
    HARD_LIMIT = 99_999_999

    def __init__(self, octopoes_connector: OctopoesAPIConnector, valid_time: datetime, report_id: str | None = None):
        self.octopoes_connector = octopoes_connector
        self.valid_time = valid_time
        self.ordered = True
        self._count = None
        self.report_id = report_id
        self.asset_reports = None

        if self.report_id and self.report_id is not None:
            asset_reports = [
                report
                for report in self.octopoes_connector.get_report(self.report_id, self.valid_time).input_oois
                if isinstance(report, AssetReport)
            ]
            self.asset_reports = sorted(asset_reports, key=lambda x: (x.report_type, x.input_ooi))

    @cached_property
    def count(self) -> int:
        if self.asset_reports is not None:
            return len(self.asset_reports)
        return self.octopoes_connector.list_reports(valid_time=self.valid_time, limit=0).count

    def __len__(self):
        return self.count

    def __getitem__(self, key: int | slice) -> Sequence[EnrichedReport | tuple[str, Report]]:
        if isinstance(key, slice):
            offset = key.start or 0
            limit = self.HARD_LIMIT
            if key.stop:
                limit = key.stop - offset

            if self.asset_reports is not None:
                return self.asset_reports[offset : offset + limit]

            reports = self.octopoes_connector.list_reports(valid_time=self.valid_time, offset=offset, limit=limit).items

            return self.enriched_report_list(reports)

        raise NotImplementedError("ReportList only supports slicing")

    def enriched_report_list(self, reports: list[HydratedReport]) -> list[EnrichedReport]:
        enriched_reports: list[EnrichedReport] = []

        for report in reports:
            enriched_report = EnrichedReport()

            enriched_report.report = report

            if settings.ASSET_REPORTS:
                asset_reports = cast(list[AssetReport], report.input_oois)

                enriched_report.total_asset_reports = len(report.input_oois)
                enriched_report.asset_reports = sorted(asset_reports[:5], key=attrgetter("name"))
                enriched_report.input_oois = list({asset_report.input_ooi for asset_report in asset_reports})
                enriched_report.report_type_summary = self.report_type_summary(asset_reports)
            else:
                enriched_report.total_asset_reports = 0
                enriched_report.input_oois = cast(list[str], report.input_oois)

            enriched_report.total_objects = len(enriched_report.input_oois)

            # We want to show only 5 children reports
            enriched_reports.append(enriched_report)

        return enriched_reports

    @staticmethod
    def report_type_summary(reports: list[AssetReport]) -> dict[str, int]:
        """
        Calculates per report type how many objects it consumed.
        """

        summary: dict[str, int] = {}

        for report_type in sorted({report.report_type for report in reports}):
            summary[report_type] = len([report for report in reports if report.report_type == report_type])

        return summary


class ConnectorFormMixin:
    connector_form_class: type[ObservedAtForm]
    request: HttpRequest

    def get_connector_form_kwargs(self) -> dict:
        if "observed_at" in self.request.GET:
            return {"data": self.request.GET}
        else:
            return {}

    def get_connector_form(self) -> ObservedAtForm:
        return self.connector_form_class(**self.get_connector_form_kwargs())


class SingleOOIMixin(OctopoesView):
    ooi: OOI

    def get_ooi_id(self) -> str:
        if "ooi_id" not in self.request.GET:
            raise OOIAttributeError("OOI primary key missing")

        return self.request.GET["ooi_id"]

    def get_ooi(self, pk: str | None = None) -> OOI:
        if pk is None:
            pk = self.get_ooi_id()

        return self.get_single_ooi(pk)

    def get_breadcrumb_list(self):
        start = {"url": reverse("ooi_list", kwargs={"organization_code": self.organization.code}), "text": "Objects"}
        if isinstance(self.ooi, Finding):
            start = {
                "url": reverse("finding_list", kwargs={"organization_code": self.organization.code}),
                "text": "Findings",
            }

        return [
            start,
            {
                "url": get_ooi_url("ooi_detail", self.ooi.primary_key, self.organization.code),
                "text": self.ooi.human_readable,
            },
        ]

    def get_ooi_properties(self, ooi: OOI) -> dict:
        class_relations = get_relations(ooi.__class__)
        props = {field_name: value for field_name, value in ooi if field_name not in class_relations}

        knowledge_base = get_knowledge_base_data_for_ooi_store({ooi.primary_key: ooi})

        if knowledge_base[ooi.get_information_id()]:
            props.update(knowledge_base[ooi.get_information_id()])

        props.pop("scan_profile")
        props.pop("primary_key")
        if "user_id" in props and props["user_id"]:
            try:
                props["user_id"] = get_user_model().objects.get(id=props["user_id"])
            except KATUser.DoesNotExist:
                props["user_id"] = None
            props = {"owner" if key == "user_id" else key: value for key, value in props.items()}
        else:
            props.pop("user_id")

        return props


class SingleOOITreeMixin(SingleOOIMixin):
    @cached_property
    def tree(self) -> ReferenceTree:
        return self.get_ooi_tree(depth=2)

    def get_depth(self):
        try:
            return min(int(self.request.GET.get("depth", DEPTH_DEFAULT)), DEPTH_MAX)
        except ValueError:
            return DEPTH_DEFAULT

    def get_ooi_tree(self, pk: str | None = None, observed_at: datetime | None = None, depth: int | None = None) -> OOI:
        if pk is None:
            pk = self.get_ooi_id()

        if observed_at is None:
            observed_at = self.observed_at

        ref = Reference.from_str(pk)
        depth = depth or self.get_depth()

        try:
            tree = self.octopoes_api_connector.get_tree(ref, valid_time=observed_at, depth=depth)
        except Exception as e:
            self.handle_connector_exception(e)

        return tree


class SeveritiesMixin:
    request: HttpRequest

    def get_severities(self) -> set[RiskLevelSeverity]:
        severities = set()
        for severity in self.request.GET.getlist("severity"):
            try:
                severities.add(RiskLevelSeverity(severity))
            except ValueError as e:
                messages.error(self.request, _(str(e)))

        return severities


class AddDashboardItemFormMixin(FormMixin):
    add_dashboard_item_form: type[forms.Form] | None = None
    organization: Organization
    template_name: str
    organization_member: OrganizationMember
    request: HttpRequest

    def get_form_class(self):
        """Specific naming for forms, so that it does not interferre with other forms."""
        if self.add_dashboard_item_form is None:
            raise ImproperlyConfigured(f"{self.__class__.__name__} requires 'dashboard_form_class' to be set.")
        return self.add_dashboard_item_form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def get_initial(self):
        """This will initiate all filters set by GET request parameters."""
        initial = {}
        for key in self.request.GET:
            values = self.request.GET.getlist(key)
            initial[key] = values if len(values) > 1 else values[0]
        return initial

    def add_to_dashboard(self) -> HttpResponse:
        if not self.organization_member.can_add_dashboard_item:
            messages.error(self.request, _("You do not have the permission to add items to a dashboard."))
            raise PermissionDenied

        form = self.get_form()
        if form.is_valid():
            dashboard_id = form.cleaned_data.get("dashboard")
            messages.success(self.request, _("Dashboard item has been added."))
            return redirect(
                reverse(
                    "organization_crisis_room", kwargs={"organization_code": self.organization.code, "id": dashboard_id}
                )
            )

        # If this mixin is used together with ListView, they will clash,
        # it must return invalid form with get_queryset from ListView so they can work together.
        if isinstance(self, ListView):
            self.object_list = self.get_queryset()
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["add_dashboard_item_form"] = self.get_form()
        return context
