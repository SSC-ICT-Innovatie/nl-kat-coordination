from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _
from strenum import StrEnum

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


class SystemType(StrEnum):
    WEB = "Web"
    MAIL = "Mail"
    DICOM = "Dicom"
    DNS = "DNS"
    OTHER = "Other"


@dataclass
class System:
    system_types: list
    oois: list


SERVICE_MAPPING = {
    "http": SystemType.WEB,
    "http-alt": SystemType.WEB,
    "https": SystemType.WEB,
    "https-alt": SystemType.WEB,
    "domain": SystemType.DNS,
    "smtp": SystemType.MAIL,
    "smtps": SystemType.MAIL,
    "submission": SystemType.MAIL,
    "imap": SystemType.MAIL,
    "imaps": SystemType.MAIL,
    "pop3": SystemType.MAIL,
    "pop3s": SystemType.MAIL,
    "dicom": SystemType.DICOM,
    "dicom-tls": SystemType.DICOM,
    "dicom-iscl": SystemType.DICOM,
}


SOFTWARE_MAPPING = {"DICOM": SystemType.DICOM}


class SystemReport(Report):
    id = "systems-report"
    name = _("System Report")
    description = _("Combine IP addresses, hostnames and services into systems.")
    plugins = {"required": {"dns-records", "nmap"}, "optional": {"nmap-udp"}}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "systems_report/report.html"
    label_style = "6-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        ips_by_input_ooi = self.to_ips(input_oois, valid_time)
        all_ips = list({ip for key, ips in ips_by_input_ooi.items() for ip in ips})

        hostnames_by_source = self.group_by_source(
            self.octopoes_api_connector.query_many(
                "IPAddress.<address[is ResolvedHostname].hostname", valid_time, all_ips
            )
        )
        services_by_source = {
            source: [SERVICE_MAPPING.get(str(service.name), SystemType.OTHER) for service in services]
            for source, services in self.group_by_source(
                self.octopoes_api_connector.query_many(
                    "IPAddress.<address[is IPPort].<ip_port [is IPService].service", valid_time, all_ips
                )
            ).items()
        }
        software_by_source = {
            source: [
                SOFTWARE_MAPPING[str(software.name)] for software in sw_instances if software.name in SOFTWARE_MAPPING
            ]
            for source, sw_instances in self.group_by_source(
                self.octopoes_api_connector.query_many(
                    "IPAddress.<address[is IPPort].<ooi [is SoftwareInstance].software", valid_time, all_ips
                )
            ).items()
        }
        websites_by_source = self.group_by_source(
            self.octopoes_api_connector.query_many(
                "IPAddress.<address[is IPPort].<ip_port [is IPService].<ip_service [is Website]", valid_time, all_ips
            )
        )

        result = {}

        for input_ooi, ips in ips_by_input_ooi.items():
            ip_services: dict[str, dict[str, Any]] = {}

            for ip in ips:
                ip_services[ip] = {
                    "hostnames": [hostname.reference for hostname in hostnames_by_source.get(ip, [])],
                    "services": list(set(services_by_source.get(ip, [])).union(set(software_by_source.get(ip, [])))),
                }

                if websites_by_source.get(ip) and SystemType.WEB not in ip_services[ip]["services"]:
                    ip_services[ip]["services"].append(SystemType.WEB)

                ip_services[ip]["services"].sort()

            domains = set()
            for data in ip_services.values():
                domains.update(data["hostnames"])

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "services": ip_services,
                "summary": {"total_systems": len(ip_services), "total_domains": len(domains)},
            }

        return result
