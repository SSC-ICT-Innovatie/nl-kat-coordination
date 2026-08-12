from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import KATFindingType, RiskLevelSeverity
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report


@dataclass
class WebCheck:
    has_csp: bool = False
    has_no_csp_vulnerabilities: bool = False
    redirects_http_https: bool = False
    offers_https: bool = False
    has_security_txt: bool = False
    no_uncommon_ports: bool = False
    has_certificates: bool = False
    certificates_not_expired: bool = False
    certificates_not_expiring_soon: bool = False

    def __bool__(self):
        return (
            self.has_csp
            and self.has_no_csp_vulnerabilities
            and self.redirects_http_https
            and self.offers_https
            and self.has_security_txt
            and self.no_uncommon_ports
            and self.has_certificates
            and self.certificates_not_expired
            and self.certificates_not_expiring_soon
        )


@dataclass
class WebChecks:
    checks: list[WebCheck] = field(default_factory=list)

    @property
    def has_csp(self):
        return sum([check.has_csp for check in self.checks])

    @property
    def has_no_csp_vulnerabilities(self):
        return sum([check.has_no_csp_vulnerabilities for check in self.checks])

    @property
    def redirects_http_https(self):
        return sum([check.redirects_http_https for check in self.checks])

    @property
    def offers_https(self):
        return sum([check.offers_https for check in self.checks])

    @property
    def has_security_txt(self):
        return sum([check.has_security_txt for check in self.checks])

    @property
    def no_uncommon_ports(self):
        return sum([check.no_uncommon_ports for check in self.checks])

    @property
    def has_certificates(self):
        return sum([check.has_certificates for check in self.checks])

    @property
    def certificates_not_expired(self):
        return sum([check.certificates_not_expired for check in self.checks])

    @property
    def certificates_not_expiring_soon(self):
        return sum([check.certificates_not_expiring_soon for check in self.checks])

    def __bool__(self) -> bool:
        return all(bool(check) for check in self.checks)

    def __len__(self) -> int:
        return len(self.checks)

    def __add__(self, other: WebChecks) -> WebChecks:
        return WebChecks(checks=self.checks + other.checks)


class WebSystemReport(Report):
    id = "web-system-report"
    name = _("Web System Report")
    description = _("Web System Reports check web systems on basic security standards.")
    plugins = {
        "required": {
            "nmap",
            "dns-records",
            "security_txt_downloader",
            "testssl-sh-ciphers",
            "ssl-version",
            "ssl-certificates",
            "webpage-analysis",
        },
        "optional": set(),
    }
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "web_system_report/report.html"
    label_style = "3-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        hostnames_by_input_ooi = self.to_hostnames(input_oois, valid_time)
        all_hostnames = list({h for key, hostnames in hostnames_by_input_ooi.items() for h in hostnames})

        query = "Hostname.<hostname[is Website].<website[is HTTPResource].<ooi[is Finding].finding_type"
        csp_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames), ["KAT-NO-CSP"]
        )
        query = (
            "Hostname.<hostname[is Website].<website[is HTTPResource].<resource[is HTTPHeader]"
            ".<ooi[is Finding].finding_type"
        )
        csp_vulnerabilities_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames), ["KAT-CSP-VULNERABILITIES"]
        )
        query = "Hostname.<netloc[is HostnameHTTPURL].<ooi[is Finding].finding_type"
        url_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames), ["KAT-NO-HTTPS-REDIRECT"]
        )
        query = "Hostname.<hostname[is Website].<ooi[is Finding].finding_type"
        no_certificate_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames), ["KAT-NO-CERTIFICATE"]
        )
        query = "Hostname.<hostname[is Website].<website[is SecurityTXT]"
        has_security_txt_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames)
        )
        query = "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type"
        port_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames),
            ["KAT-UNCOMMON-OPEN-PORT", "KAT-OPEN-SYSADMIN-PORT", "KAT-OPEN-DATABASE-PORT"],
        )
        query = "Hostname.<hostname[is Website].certificate.<ooi[is Finding].finding_type"
        certificate_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many(query, valid_time, all_hostnames),
            ["KAT-CERTIFICATE-EXPIRED", "KAT-CERTIFICATE-EXPIRING-SOON"],
        )

        result = {ooi: {"input_ooi": ooi, "web_checks": WebChecks(), "finding_types": []} for ooi in input_oois}

        for input_ooi, hostname_references in hostnames_by_input_ooi.items():
            finding_types = {}
            checks = WebChecks()

            for hostname in hostname_references:
                check = WebCheck()
                check.has_csp = not any(csp_finding_types.get(hostname, []))
                check.has_no_csp_vulnerabilities = check.has_csp and not any(
                    csp_vulnerabilities_finding_types.get(hostname, [])
                )
                check.redirects_http_https = not any(url_finding_types.get(hostname, []))
                check.offers_https = not any(no_certificate_finding_types.get(hostname, []))
                check.has_security_txt = bool(has_security_txt_finding_types.get(hostname, []))
                security_txt_finding_types = [
                    KATFindingType(
                        id="KAT-NO-SECURITY-TXT",
                        description="This hostname does not have a Security.txt file.",
                        risk_severity=RiskLevelSeverity.RECOMMENDATION,
                        recommendation="Make sure there is a security.txt available.",
                    )
                ]

                check.no_uncommon_ports = not any(port_finding_types.get(hostname, []))
                check.has_certificates = check.offers_https
                check.certificates_not_expired = check.has_certificates and "KAT-CERTIFICATE-EXPIRED" not in [
                    x.id for x in certificate_finding_types.get(hostname, [])
                ]
                check.certificates_not_expiring_soon = (
                    check.has_certificates
                    and "KAT-CERTIFICATE-EXPIRING-SOON"
                    not in [x.id for x in certificate_finding_types.get(hostname, [])]
                )

                checks.checks.append(check)
                new_types = (
                    csp_finding_types.get(hostname, [])
                    + csp_vulnerabilities_finding_types.get(hostname, [])
                    + url_finding_types.get(hostname, [])
                    + no_certificate_finding_types.get(hostname, [])
                    + port_finding_types.get(hostname, [])
                    + certificate_finding_types.get(hostname, [])
                    + security_txt_finding_types
                )

                for finding_type in new_types:
                    if finding_type.risk_severity not in [None, RiskLevelSeverity.PENDING] and finding_type.description:
                        finding_types[finding_type.id] = finding_type

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "web_checks": checks,
                # We need cast here because mypy doesn't understand that we only add finding_types
                # when risk level severity isn't None
                "finding_types": sorted(
                    finding_types.values(), reverse=True, key=lambda x: cast(RiskLevelSeverity, x.risk_severity)
                ),
            }

        return result
