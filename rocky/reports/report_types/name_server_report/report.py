from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import RiskLevelSeverity
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


@dataclass
class NameServerCheck:
    no_uncommon_ports: bool = False
    has_dnssec: bool = False
    has_valid_dnssec: bool = False

    def __bool__(self):
        return self.no_uncommon_ports and self.has_dnssec and self.has_valid_dnssec


@dataclass
class NameServerChecks:
    checks: list[NameServerCheck] = field(default_factory=list)

    @property
    def no_uncommon_ports(self):
        return sum([check.no_uncommon_ports for check in self.checks])

    @property
    def has_dnssec(self):
        return sum([check.has_dnssec for check in self.checks])

    @property
    def has_valid_dnssec(self):
        return sum([check.has_valid_dnssec for check in self.checks])

    def __bool__(self) -> bool:
        return all(bool(check) for check in self.checks)

    def __len__(self) -> int:
        return len(self.checks)

    def __add__(self, other: NameServerChecks) -> NameServerChecks:
        return NameServerChecks(checks=self.checks + other.checks)


class NameServerSystemReport(Report):
    id = "name-server-report"
    name = _("Name Server Report")
    description = _("Name Server Report checks name servers on basic security standards.")
    plugins = {"required": {"nmap", "dns-records", "dns-sec"}, "optional": set()}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "name_server_report/report.html"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        hostnames_by_input_ooi = self.to_hostnames(input_oois, valid_time)
        all_hostnames = list({h for key, hostnames in hostnames_by_input_ooi.items() for h in hostnames})

        query = "Hostname.<ooi[is Finding].finding_type"
        hostname_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames),
            ["KAT-NO-DNSSEC", "KAT-INVALID-DNSSEC"],
        )
        query = "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type"
        port_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames),
            ["KAT-UNCOMMON-OPEN-PORT", "KAT-OPEN-SYSADMIN-PORT", "KAT-OPEN-DATABASE-PORT"],
        )

        result = {
            ooi: {"input_ooi": ooi, "name_server_checks": NameServerChecks(), "finding_types": []} for ooi in input_oois
        }

        for input_ooi, hostname_references in hostnames_by_input_ooi.items():
            finding_types = {}
            checks = NameServerChecks()
            for hostname in hostname_references:
                check = NameServerCheck()
                check.no_uncommon_ports = not any(port_finding_types.get(hostname, []))
                check.has_dnssec = "KAT-NO-DNSSEC" not in [x.id for x in hostname_finding_types.get(hostname, [])]
                check.has_valid_dnssec = check.has_dnssec and "KAT-INVALID-DNSSEC" not in [
                    x.id for x in hostname_finding_types.get(hostname, [])
                ]

                checks.checks.append(check)

                for finding_type in port_finding_types.get(hostname, []) + hostname_finding_types.get(hostname, []):
                    if finding_type.risk_severity not in [None, RiskLevelSeverity.PENDING] and finding_type.description:
                        finding_types[finding_type.id] = finding_type

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "name_server_checks": checks,
                # We need cast here because mypy doesn't understand that we only add finding_types
                # when risk level severity isn't None
                "finding_types": sorted(
                    finding_types.values(), reverse=True, key=lambda x: cast(RiskLevelSeverity, x.risk_severity)
                ),
            }

        return result
