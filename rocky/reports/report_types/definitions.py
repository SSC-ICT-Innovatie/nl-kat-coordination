from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, TypeVar

from django.utils.functional import Promise

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import OOI, Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from octopoes.models.types import OOIType

REPORTS_DIR = Path(__file__).parent


class ReportPlugins(TypedDict):
    required: set[str]
    optional: set[str]


def report_plugins_union(report_types: list[type["BaseReport"]]) -> ReportPlugins:
    """Take the union of the required and optional plugin sets and remove optional plugins that are required"""

    plugins: ReportPlugins = {"required": set(), "optional": set()}

    for report_type in report_types:
        plugins["required"].update(report_type.plugins["required"])
        plugins["optional"].update(report_type.plugins["optional"])
        plugins["optional"].difference_update(report_type.plugins["required"])

    return plugins


class BaseReport:
    id: str
    name: Promise
    description: Promise
    template_path: str = "report.html"
    plugins: ReportPlugins
    input_ooi_types: set[type[OOI]]
    label_style = "1-light"  # default/fallback color

    def __init__(self, octopoes_api_connector: OctopoesAPIConnector):
        self.octopoes_api_connector = octopoes_api_connector

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        raise NotImplementedError

    @classmethod
    def class_attributes(cls) -> dict[str, Any]:
        return {
            "id": cls.id,
            "name": cls.name,
            "description": cls.description,
            "plugins": cls.plugins,
            "input_ooi_types": cls.input_ooi_types,
            "template_path": cls.template_path,
            "label_style": cls.label_style,
        }


BaseReportType = TypeVar("BaseReportType", bound="BaseReport")


class Report(BaseReport):
    def generate_data(self, input_ooi: str, valid_time: datetime) -> dict[str, Any]:
        raise NotImplementedError

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        """Generate data for multiple OOIs. Child classes can override this method to improve performance."""

        return {input_ooi: self.generate_data(input_ooi, valid_time) for input_ooi in input_oois}

    @staticmethod
    def group_by_source(
        query_result: list[tuple[str, OOIType]], check: Callable[[OOIType], bool] | None = None
    ) -> dict[str, list[OOIType]]:
        """Transform a query-many result from [(ref1, obj1), (ref1, obj2), ...] into {ref1: [obj1, obj2], ...}"""

        result: dict[str, list[OOIType]] = {}

        for source, ooi in query_result:
            if source not in result:
                result[source] = []

            if not check or check(ooi):
                result[source].append(ooi)

        return result

    @staticmethod
    def group_finding_types_by_source(
        query_result: list[tuple[str, OOIType]], keep_ids: list[str] | None = None
    ) -> dict[str, list[OOIType]]:
        if keep_ids:
            return Report.group_by_source(query_result, lambda x: x.id in keep_ids)

        return Report.group_by_source(query_result)

    def to_hostnames(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, list[Reference]]:
        """
        Turn a list of either Hostname and IPAddress references into a list of related hostnames, grouped by input ooi.

        If an input ooi is an IP without hostnames, the key will still be present but the list will be empty.
        """

        hostnames_by_input_ooi = {ref: [ref] if ref.class_type == Hostname else [] for ref in input_oois}
        ip_refs = [ref for ref in input_oois if ref.class_type in (IPAddressV4, IPAddressV6)]

        for input_ooi, ip_hostname in self.octopoes_api_connector.query_many(
            "IPAddress.<address[is ResolvedHostname].hostname", valid_time, ip_refs
        ):
            if input_ooi not in hostnames_by_input_ooi:
                hostnames_by_input_ooi[Reference.from_str(input_ooi)] = []

            hostnames_by_input_ooi[Reference.from_str(input_ooi)].append(ip_hostname.reference)

        return hostnames_by_input_ooi

    @staticmethod
    def hostnames_to_human_readable(hostnames_by_input_ooi: dict) -> dict[str, str]:
        """Converts input_oois to human readable hostname strings.

        Turns a list of either Hostname and IPAddress references into a string
        of shortest related hostname and indication on more hostnames present,
        grouped by input ooi.
        """
        return {
            input_ooi: (
                f'({min([h.human_readable for h in hostnames], key=len)}{", ..." if len(hostnames) > 1 else ""})'
                if hostnames
                else ""
            )
            for input_ooi, hostnames in hostnames_by_input_ooi.items()
        }

    def to_ips(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, list[Reference]]:
        """
        Turn a list of either Hostname and IPAddress reference strings into a list of related ips.

        If an input ooi is a Hostname without ips, the key will still be present but the list will be empty.
        """

        ips_by_input_ooi = {ref: [ref] if ref.class_type in [IPAddressV4, IPAddressV6] else [] for ref in input_oois}
        hostname_refs = [ref for ref in input_oois if ref.class_type == Hostname]

        for input_ooi, hostname_ip in self.octopoes_api_connector.query_many(
            "Hostname.<hostname[is ResolvedHostname].address", valid_time, hostname_refs
        ):
            if input_ooi not in ips_by_input_ooi:
                ips_by_input_ooi[Reference.from_str(input_ooi)] = []

            ips_by_input_ooi[Reference.from_str(input_ooi)].append(hostname_ip.reference)

        return ips_by_input_ooi


class MultiReport(BaseReport):
    def post_process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class AggregateReportSubReports(TypedDict):
    required: list[type[Report]]
    optional: list[type[Report]]


class AggregateReport(BaseReport):
    reports: AggregateReportSubReports

    def post_process_data(self, data: dict[str, Any], valid_time: datetime, organization_code: str) -> dict[str, Any]:
        raise NotImplementedError


class ReportType(TypedDict):
    id: str
    name: str
    description: str
    label_style: str
