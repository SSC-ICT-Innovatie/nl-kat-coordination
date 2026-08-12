from collections.abc import Iterable
from datetime import datetime
from typing import Any, TypedDict

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


class RPKIData(TypedDict):
    exists: bool
    valid: bool


class RPKIReport(Report):
    id = "rpki-report"
    name = _("RPKI Report")
    description = _(
        "Shows whether the IP is covered by a valid RPKI ROA. For a hostname it shows "
        "the IP addresses and whether they are covered by a valid RPKI ROA."
    )
    plugins = {"required": {"dns-records", "rpki"}, "optional": set()}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "rpki_report/report.html"
    label_style = "4-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        ips_by_input_ooi = self.to_ips(input_oois, valid_time)
        all_ips = list({ip for key, ips in ips_by_input_ooi.items() for ip in ips})
        finding_types_by_source = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many("IPAddress.<ooi[is Finding].finding_type", valid_time, all_ips)
        )

        result = {}

        for input_ooi, ips in ips_by_input_ooi.items():
            rpki_ips: dict[Reference, RPKIData] = {}
            number_of_ips = len(ips)
            number_of_compliant = number_of_ips
            number_of_available = number_of_ips
            number_of_valid = number_of_ips

            for ip in ips:
                finding_types = finding_types_by_source.get(ip, [])
                exists = not any(finding_type for finding_type in finding_types if finding_type.id in ["KAT-NO-RPKI"])
                invalid = any(finding_type for finding_type in finding_types if finding_type.id in ["KAT-INVALID-RPKI"])
                rpki_ips[ip] = {"exists": exists, "valid": not invalid}
                number_of_available -= 1 if not exists else 0
                number_of_valid -= 1 if invalid else 0
                number_of_compliant -= 1 if not (exists and not invalid) else 0

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "rpki_ips": rpki_ips,
                "number_of_available": number_of_available,
                "number_of_compliant": number_of_compliant,
                "number_of_valid": number_of_valid,
                "number_of_ips": number_of_ips,
            }

        return result
