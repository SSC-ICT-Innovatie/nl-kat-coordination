from octopoes.models import OOI, Reference
from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.concatenated_report.report import ConcatenatedReport
from reports.report_types.definitions import AggregateReport, BaseReport, Report
from reports.report_types.dns_report.report import DNSReport
from reports.report_types.findings_report.report import FindingsReport
from reports.report_types.ipv6_report.report import IPv6Report
from reports.report_types.mail_report.report import MailReport
from reports.report_types.multi_organization_report.report import MultiOrganizationReport
from reports.report_types.name_server_report.report import NameServerSystemReport
from reports.report_types.open_ports_report.report import OpenPortsReport
from reports.report_types.rpki_report.report import RPKIReport
from reports.report_types.safe_connections_report.report import SafeConnectionsReport
from reports.report_types.systems_report.report import SystemReport
from reports.report_types.tls_report.report import TLSReport
from reports.report_types.vulnerability_report.report import VulnerabilityReport
from reports.report_types.web_system_report.report import WebSystemReport

REPORTS = [
    FindingsReport,
    VulnerabilityReport,
    OpenPortsReport,
    WebSystemReport,
    SafeConnectionsReport,
    TLSReport,
    SystemReport,
    DNSReport,
    MailReport,
    NameServerSystemReport,
    RPKIReport,
    IPv6Report,
]
AGGREGATE_REPORTS = [AggregateOrganisationReport]

MULTI_REPORTS = [MultiOrganizationReport]

CONCATENATED_REPORTS = [ConcatenatedReport]

ALL_REPORT_TYPES = REPORTS + AGGREGATE_REPORTS + MULTI_REPORTS + CONCATENATED_REPORTS


def get_ooi_types_with_report() -> set[type[OOI]]:
    """
    Get all OOI types that have a report
    """
    return {ooi_type for report in REPORTS for ooi_type in report.input_ooi_types}


def get_report_types_for_ooi(ooi_pk: str) -> set[type[BaseReport]]:
    """
    Get all report types that can be generated for a given OOI
    """
    reference = Reference.from_str(ooi_pk)
    ooi_type = reference.class_type
    return {report for report in REPORTS if ooi_type in report.input_ooi_types}


def get_report_types_for_oois(oois: list[str]) -> set[type[BaseReport]]:
    """
    Get all report types that can be generated for a given list of OOIs
    """
    return {report for ooi_pk in oois for report in get_report_types_for_ooi(ooi_pk)}


def get_report_types_for_ooi_type(ooi_type: type[OOI]) -> set[type[BaseReport]]:
    """
    Get all report types that can be generated for a given OOI type
    """
    return {report for report in REPORTS if ooi_type in report.input_ooi_types}


def get_report_types_for_ooi_types(ooi_types: set[type[OOI]]) -> set[type[BaseReport]]:
    """
    Get all report types that can be generated for a given list of OOI types
    """
    return {report for ooi_type in ooi_types for report in get_report_types_for_ooi_type(ooi_type)}


def get_report_by_id(report_id: str) -> type[BaseReport]:
    """
    Get report type by id
    """

    for report in ALL_REPORT_TYPES:
        if report.id == report_id:
            return report
    raise ValueError(f"Report with id {report_id} not found")


def get_reports(report_ids: list[str]) -> list[type[BaseReport]]:
    return [get_report_by_id(report_id) for report_id in report_ids]


def get_plugins_for_report_ids(reports: list[str]) -> dict[str, set[str]]:
    """
    Get all boefjes that are required and optional for a given list of reports
    """
    required_boefjes: set[str] = set()
    optional_boefjes: set[str] = set()

    for report in get_reports(reports):
        required_boefjes.update(report.plugins["required"])
        optional_boefjes.update(report.plugins["optional"])

    return {"required": required_boefjes, "optional": optional_boefjes}


def get_report_types_from_aggregate_report(aggregate_report: type[AggregateReport]) -> dict[str, set[type[Report]]]:
    required_reports = set()
    optional_reports = set()

    required_reports.update(aggregate_report.reports["required"])
    optional_reports.update(aggregate_report.reports["optional"])

    return {"required": required_reports, "optional": optional_reports}


def get_ooi_types_from_aggregate_report(aggregate_report: type[AggregateReport]) -> set[type[OOI]]:
    ooi_types = set()
    for reports in aggregate_report.reports.values():
        # Mypy doesn't support TypedDict and .values()
        # https://github.com/python/mypy/issues/7981
        for report in reports:  # type: ignore[attr-defined]
            ooi_types.update(report.input_ooi_types)
    return ooi_types
