from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


@dataclass
class System:
    system_types: list
    oois: list


class IPv6Report(Report):
    id = "ipv6-report"
    name = _("IPv6 Report")
    description = _("Check whether hostnames point to IPv6 addresses.")
    plugins = {"required": {"dns-records"}, "optional": set()}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "ipv6_report/report.html"
    label_style = "4-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        """
        For hostnames, check whether they point to ipv6 addresses.
        For ip addresses, check all hostnames that point to them, and check whether they point to ipv6 addresses.
        """
        hostnames_by_input_ooi = self.to_hostnames(input_oois, valid_time)
        all_hostnames = list({h for key, hostnames in hostnames_by_input_ooi.items() for h in hostnames})

        query = "Hostname.<hostname[is ResolvedHostname].address"
        ips = self.group_by_source(self.octopoes_api_connector.query_many(query, valid_time, all_hostnames))

        result: dict[Reference, dict[str, Any]] = {ooi: {} for ooi in input_oois}
        for input_ooi, hostnames in hostnames_by_input_ooi.items():
            result[input_ooi] = {
                hostname_ref.tokenized.name: {
                    "enabled": any(ip.reference.class_type == IPAddressV6 for ip in ips.get(hostname_ref, []))
                }
                for hostname_ref in hostnames
            }

        return result
