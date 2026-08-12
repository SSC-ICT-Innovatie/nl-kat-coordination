from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


class OpenPortsReport(Report):
    id = "open-ports-report"
    name = _("Open Ports Report")
    description = _("Find open ports of IP addresses")
    plugins = {"required": {"nmap"}, "optional": {"shodan", "nmap-udp", "nmap-ports", "nmap-ip-range", "masscan"}}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "open_ports_report/report.html"
    label_style = "5-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        ips_by_input_ooi = self.to_ips(input_oois, valid_time)
        all_ips = list({ip for key, ips in ips_by_input_ooi.items() for ip in ips})
        ports_by_source = self.group_by_source(
            self.octopoes_api_connector.query_many("IPAddress.<address[is IPPort]", valid_time, all_ips)
        )
        all_ports = [port for key, ports in ports_by_source.items() for port in ports]

        hostnames_by_source = self.group_by_source(
            self.octopoes_api_connector.query_many(
                "IPAddress.<address[is ResolvedHostname].hostname", valid_time, all_ips
            )
        )
        services_by_port = self.group_by_source(
            self.octopoes_api_connector.query_many("IPPort.<ip_port[is IPService].service", valid_time, all_ports)
        )
        result = {}

        for input_ooi, ips in ips_by_input_ooi.items():
            by_ip = {}

            for ip in ips:
                ports = ports_by_source.get(ip, [])
                hostnames = [h.name for h in hostnames_by_source.get(ip, [])]

                port_numbers = {}
                services = {}

                for port in ports:
                    origins = self.octopoes_api_connector.list_origins(result=port.reference, valid_time=valid_time)
                    found_by_openkat = any(o.method in ("kat_nmap_normalize", "kat_masscan_normalize") for o in origins)
                    port_numbers[port.port] = found_by_openkat
                    services[port.port] = [service.name for service in services_by_port.get(port.reference, [])]

                sorted_port_numbers = dict(sorted(port_numbers.items()))
                by_ip[ip.tokenized.address] = {
                    "ports": sorted_port_numbers,
                    "hostnames": hostnames,
                    "services": services,
                }

            result[input_ooi] = by_ip
        return result
