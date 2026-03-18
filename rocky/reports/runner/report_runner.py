from datetime import datetime, timezone
from string import Template
from typing import Any

import structlog
from django.conf import settings
from pydantic import RootModel
from tools.models import Organization
from tools.ooi_helpers import create_ooi

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference, ScanLevel, ScanProfileType
from octopoes.models.exception import ObjectNotFoundException, TypeNotFound
from octopoes.models.ooi.reports import AssetReport, Report, ReportRecipe
from octopoes.models.types import type_by_name
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.definitions import ReportPlugins, report_plugins_union
from reports.report_types.helpers import get_report_by_id
from reports.report_types.multi_organization_report.report import MultiOrganizationReport, collect_report_data
from reports.runner.models import ReportRunner
from rocky.bytes_client import BytesClient
from rocky.scheduler import ReportTask

logger = structlog.get_logger(__name__)


class LocalReportRunner(ReportRunner):
    def __init__(self, bytes_client: BytesClient, valid_time: datetime | None = None):
        self.bytes_client = bytes_client
        self.valid_time = valid_time

    def run(self, report_task: ReportTask) -> None:
        organization = Organization.objects.get(code=report_task.organisation_id)
        # TODO: https://github.com/minvws/nl-kat-coordination/issues/4014
        valid_time = self.valid_time or datetime.now(timezone.utc)
        connector = OctopoesAPIConnector(
            settings.OCTOPOES_API, report_task.organisation_id, timeout=settings.ROCKY_OUTGOING_REQUEST_TIMEOUT
        )
        recipe = connector.get(Reference.from_str(f"ReportRecipe|{report_task.report_recipe_id}"), valid_time)

        if input_oois := recipe.input_recipe.get("input_oois"):
            ooi_pks = list({Reference.from_str(ooi) for ooi in input_oois})
        elif query := recipe.input_recipe.get("query"):
            oois = connector.list_objects(
                types={type_by_name(ooi_type) for ooi_type in query["ooi_types"]},
                valid_time=datetime.now(tz=timezone.utc),
                scan_level={ScanLevel(level) for level in query["scan_level"]},
                scan_profile_type={ScanProfileType(scan_type) for scan_type in query["scan_type"]},
                search_string=query["search_string"],
                order_by=query["order_by"],
                asc_desc=query["asc_desc"],
            ).items

            ooi_pks = list({ooi.reference for ooi in oois})
        else:
            raise ValueError("Invalid recipe: no input_oois or query found")

        additional_input_data: dict[str, Any] = {}

        if recipe.report_type == AggregateOrganisationReport.id:
            _, additional_input_data, report_data, report_errors = aggregate_reports(
                connector, ooi_pks, recipe.asset_report_types, valid_time, report_task.organisation_id
            )
        elif recipe.report_type == MultiOrganizationReport.id:
            report_data_multi = collect_report_data(connector, [str(x) for x in ooi_pks], valid_time)
            report_data = {MultiOrganizationReport.id: report_data_multi}
            additional_input_data = MultiOrganizationReport(connector).post_process_data(report_data_multi)
        else:
            report_types = [get_report_by_id(report_type_id) for report_type_id in recipe.asset_report_types]
            error_reports, report_data = collect_reports(valid_time, connector, ooi_pks, report_types)

        self.bytes_client.organization = organization.code
        save_report_data(
            self.bytes_client, valid_time, connector, organization, ooi_pks, report_data, recipe, additional_input_data
        )
        self.bytes_client.organization = None


def collect_reports(
    valid_time: datetime, octopoes_connector: OctopoesAPIConnector, input_oois: list[Reference], report_types
):
    error_reports = []
    report_data: dict[str, dict[str, dict[str, Any]]] = {}
    by_type: dict[str, list[str]] = {}

    for ooi in input_oois:
        ooi_type = ooi.class_

        if ooi_type not in by_type:
            by_type[ooi_type] = []

        by_type[ooi_type].append(ooi)

    for report_class in report_types:
        oois = {ooi for ooi_type in report_class.input_ooi_types for ooi in by_type.get(ooi_type.get_object_type(), [])}

        try:
            results = report_class(octopoes_connector).collect_data(oois, valid_time)
        except ObjectNotFoundException:
            error_reports.append(report_class.id)
            continue
        except TypeNotFound:
            error_reports.append(report_class.id)
            continue

        for ooi, data in results.items():
            if report_class.id not in report_data:
                report_data[report_class.id] = {}

            report_data[report_class.id][ooi] = {
                "data": data,
                "template": report_class.template_path,
                "report_name": report_class.name,
            }

    return error_reports, report_data


def save_report_data(
    bytes_client: BytesClient,
    observed_at: datetime,
    octopoes_api_connector: OctopoesAPIConnector,
    organization: Organization,
    oois: list[Reference],
    report_data: dict,
    recipe: ReportRecipe,
    additional_input_data: dict | None = None,
) -> Report | None:
    if additional_input_data is None:
        additional_input_data = {}

    plugins = report_plugins_union([get_report_by_id(type_id) for type_id in recipe.asset_report_types])

    input_oois: list[str | Reference]

    if settings.ASSET_REPORTS:
        asset_reports = create_asset_reports(
            bytes_client, plugins, observed_at, observed_at, octopoes_api_connector, organization, recipe, report_data
        )
        input_oois = [asset_report.reference for asset_report in asset_reports]
    else:
        input_ooi_set: set[str] = set()
        for ooi_data in report_data.values():
            input_ooi_set.update(ooi for ooi in ooi_data)
        input_oois = sorted(input_ooi_set)

    input_data = {
        "input_data": {"input_oois": input_oois, "report_types": recipe.asset_report_types, "plugins": plugins}
    }

    raw_id = bytes_client.upload_raw(
        raw=ReportDataDict(input_data | additional_input_data).model_dump_json().encode(),
        manual_mime_types={"openkat/report"},
    )

    report_type_name = str(
        get_report_by_id(
            recipe.report_type if len(recipe.asset_report_types) > 1 else recipe.asset_report_types[0]
        ).name
    )
    report_name = observed_at.strftime(
        Template(recipe.report_name_format).safe_substitute(oois_count=str(len(oois)), report_type=report_type_name)
    )

    if len(oois) == 1:
        report_name = Template(report_name).safe_substitute(ooi=oois[0].human_readable)

    report_ooi = Report(
        name=report_name,
        report_type=recipe.report_type,
        template=get_report_by_id(recipe.report_type).template_path,
        organization_code=organization.code,
        organization_name=organization.name,
        organization_tags=[tag.name for tag in organization.tags.all()],
        data_raw_id=raw_id,
        date_generated=observed_at,
        reference_date=observed_at,
        input_oois=input_oois,
        observed_at=observed_at,
        report_recipe=recipe.reference,
    )

    create_ooi(octopoes_api_connector, bytes_client, report_ooi, observed_at)
    logger.info("Report created [report_type=%s]", recipe.report_type, event_code=800071, report=report_ooi)
    return report_ooi


def create_asset_reports(
    bytes_client: BytesClient,
    plugins: ReportPlugins,
    now: datetime,
    observed_at: datetime,
    octopoes_api_connector: OctopoesAPIConnector,
    organization: Organization,
    recipe: ReportRecipe,
    report_data: dict,
) -> list[AssetReport]:
    asset_reports = []

    for report_type_id, ooi_data in report_data.items():
        report_type = get_report_by_id(report_type_id)

        for reference, data in ooi_data.items():
            asset_report_input = {
                "input_data": {
                    "input_oois": [reference],
                    "report_types": [report_type.id],
                    "plugins": {
                        "required": {p for p in plugins["required"] if p in report_type.plugins["required"]},
                        "optional": {p for p in plugins["optional"] if p in report_type.plugins["optional"]},
                    },
                }
            }
            asset_raw_id = bytes_client.upload_raw(
                raw=ReportDataDict({"report_data": data["data"]} | asset_report_input).model_dump_json().encode(),
                manual_mime_types={"openkat/report"},
            )

            input_ooi = reference if not hasattr(reference, "human_readable") else reference.human_readable

            asset_report = AssetReport(
                name=f"{report_type.name} for {input_ooi}",
                report_type=report_type_id,
                report_recipe=recipe.reference,
                template=report_type.template_path,
                organization_code=organization.code,
                organization_name=organization.name,
                organization_tags=[tag.name for tag in organization.tags.all()],
                data_raw_id=asset_raw_id,
                date_generated=now,
                reference_date=observed_at,
                input_ooi=reference,
                observed_at=observed_at,
            )
            create_ooi(octopoes_api_connector, bytes_client, asset_report, observed_at)
            asset_reports.append(asset_report)

    return asset_reports


class ReportDataDict(RootModel):
    root: Any

    class Config:
        arbitrary_types_allowed = True


def aggregate_reports(
    connector: OctopoesAPIConnector,
    input_oois: list[Reference],
    selected_report_types: list[str],
    valid_time: datetime,
    organization_code: str,
) -> tuple[AggregateOrganisationReport, dict[str, Any], dict[str, Any], list[str]]:
    all_types = [
        t
        for t in AggregateOrganisationReport.reports["required"] + AggregateOrganisationReport.reports["optional"]
        if t.id in selected_report_types
    ]

    errors, report_data = collect_reports(valid_time, connector, input_oois, all_types)
    aggregate_report = AggregateOrganisationReport(connector)
    post_processed_data = aggregate_report.post_process_data(report_data, valid_time, organization_code)

    return aggregate_report, post_processed_data, report_data, errors
