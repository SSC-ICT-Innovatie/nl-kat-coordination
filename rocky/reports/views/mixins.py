from datetime import datetime, timezone

import structlog
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from tools.ooi_helpers import create_ooi

from octopoes.models import Reference
from octopoes.models.ooi.reports import Report
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.concatenated_report.report import ConcatenatedReport
from reports.report_types.helpers import REPORTS
from reports.report_types.multi_organization_report.report import MultiOrganizationReport, collect_report_data
from reports.runner.report_runner import ReportDataDict, aggregate_reports, collect_reports, save_report_data
from reports.views.base import BaseReportView

logger = structlog.get_logger(__name__)


class SaveGenerateReportMixin(BaseReportView):
    def save_report(self, report_names: list) -> Report | None:  # TODO: fix naming
        error_reports, report_data = collect_reports(
            self.observed_at,
            self.octopoes_api_connector,
            [Reference.from_str(ref) for ref in self.get_ooi_pks()],
            [x for x in self.get_report_types() if x in REPORTS],
        )

        report_ooi = save_report_data(
            self.bytes_client,
            self.observed_at,
            self.octopoes_api_connector,
            self.organization,
            [x.reference for x in self.get_oois()],
            report_data,
            self.create_report_recipe("${report_type} for ${oois_count} objects", ConcatenatedReport.name, None),
        )

        # If OOI could not be found or the date is incorrect, it will be shown to the user as a message error
        if error_reports:
            report_types = ", ".join(set(error_reports))
            date = self.observed_at.date()
            error_message = _("No data could be found for %(report_types). Object(s) did not exist on %(date)s.") % {
                "report_types": report_types,
                "date": date,
            }
            messages.error(self.request, error_message)

        return report_ooi


class SaveAggregateReportMixin(BaseReportView):
    def save_report(self, report_names: list) -> Report | None:
        aggregate_report, post_processed_data, report_data, report_errors = aggregate_reports(
            self.octopoes_api_connector,
            [ooi.reference for ooi in self.get_oois()],
            self.get_report_type_ids(),
            self.observed_at,
            self.organization.code,
        )

        # If OOI could not be found or the date is incorrect, it will be shown to the user as a message error
        if report_errors:
            report_types = ", ".join(set(report_errors))
            date = self.observed_at.date()
            error_message = _("No data could be found for %(report_types). Object(s) did not exist on %(date)s.") % {
                "report_types": report_types,
                "date": date,
            }
            messages.add_message(self.request, messages.ERROR, error_message)

        return save_report_data(
            self.bytes_client,
            self.get_observed_at(),
            self.octopoes_api_connector,
            self.organization,
            [ooi.reference for ooi in self.get_oois()],
            report_data,
            self.create_report_recipe(
                "${report_type} for ${oois_count} objects", AggregateOrganisationReport.name, None
            ),
            post_processed_data,
        )


class SaveMultiReportMixin(BaseReportView):
    def save_report(self, report_names: list) -> Report:
        now = datetime.now(timezone.utc)

        observed_at = self.get_observed_at()
        report_type = MultiOrganizationReport(self.octopoes_api_connector)

        name = now.strftime(report_names[0][1])
        if not name or name.isspace():
            name = report_type.name

        report_data = report_type.post_process_data(
            collect_report_data(self.octopoes_api_connector, self.get_ooi_pks(), self.observed_at)
        )
        report_data_raw_id = self.bytes_client.upload_raw(
            ReportDataDict(report_data | self.get_input_data()).model_dump_json().encode(),
            manual_mime_types={"openkat/report"},
        )

        report_ooi = Report(
            name=str(name),
            report_type=str(report_type.id),
            template=report_type.template_path,
            organization_code=self.organization.code,
            organization_name=self.organization.name,
            organization_tags=set(self.organization.tags.all()),
            data_raw_id=report_data_raw_id,
            date_generated=now,
            reference_date=observed_at,  # TODO: https://github.com/minvws/nl-kat-coordination/issues/4014
            input_oois=self.get_ooi_pks(),
            observed_at=observed_at,
        )

        create_ooi(self.octopoes_api_connector, self.bytes_client, report_ooi, observed_at)
        logger.info("Report created", event_code=800071, report=report_ooi)

        return report_ooi
