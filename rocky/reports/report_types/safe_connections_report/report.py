from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report

CIPHER_FINDINGS = ["KAT-RECOMMENDATION-BAD-CIPHER", "KAT-MEDIUM-BAD-CIPHER", "KAT-CRITICAL-BAD-CIPHER"]


class SafeConnectionsReport(Report):
    id = "safe-connections-report"
    name = _("Safe Connections Report")
    description: str = _("Shows whether the IPService contains safe ciphers.")
    plugins = {"required": {"dns-records", "testssl-sh-ciphers", "nmap"}, "optional": set()}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "safe_connections_report/report.html"
    label_style = "2-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        ips_by_input_ooi = self.to_ips(input_oois, valid_time)
        all_ips = list({ip for key, ips in ips_by_input_ooi.items() for ip in ips})

        finding_types_by_source = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(
                "IPAddress.<address[is IPPort].<ip_port [is IPService]"
                ".<ip_service [is TLSCipher].<ooi[is Finding].finding_type",
                valid_time,
                all_ips,
            ),
            CIPHER_FINDINGS,
        )

        result = {}

        for input_ooi, ips in ips_by_input_ooi.items():
            sc_ips = {}
            number_of_ips = len(ips)
            number_of_available = number_of_ips

            for ip in ips:
                sc_ips[ip] = finding_types_by_source.get(ip, [])
                number_of_available -= 1 if sc_ips[ip] else 0

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "sc_ips": sc_ips,
                "number_of_available": number_of_available,
                "number_of_ips": number_of_ips,
            }

        return result
