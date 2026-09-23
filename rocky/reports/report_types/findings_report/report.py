from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, FindingType, RiskLevelSeverity
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from octopoes.models.ooi.web import URL
from reports.report_types.definitions import Report, ReportPlugins

TREE_DEPTH = 9
SEVERITY_OPTIONS = [severity.value for severity in RiskLevelSeverity]


class FindingsReport(Report):
    id = "findings-report"
    name = _("Findings Report")
    description = _("Shows all the finding types and their occurrences.")
    plugins: ReportPlugins = {
        "required": {
            "dns-records",
            "nmap",
            "nmap-udp",
            "webpage-analysis",
            "ssl-version",
            "ssl-certificates",
            "testssl-sh-ciphers",
        },
        "optional": {"snyk", "service_banner", "shodan", "leakix"},
    }
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6, URL}
    template_path = "findings_report/report.html"
    label_style = "3-light"

    def generate_data(self, input_ooi: str, valid_time: datetime) -> dict[str, Any]:
        reference = Reference.from_str(input_ooi)
        findings = []
        finding_types: dict[str, Any] = {}
        total_by_severity = {}
        total_by_severity_per_finding_type = {}
        history_cache = {}

        for severity in SEVERITY_OPTIONS:
            total_by_severity[severity] = 0
            total_by_severity_per_finding_type[severity] = 0

        tree = self.octopoes_api_connector.get_tree(
            reference, depth=TREE_DEPTH, types={Finding}, valid_time=valid_time
        ).store

        findings = [ooi for ooi in tree.values() if ooi.ooi_type == "Finding"]
        all_finding_types = self.octopoes_api_connector.list_objects(types={FindingType}, valid_time=valid_time).items

        for finding in findings:
            try:
                finding_type = next(filter(lambda x: x.id == finding.finding_type.tokenized.id, all_finding_types))
            except StopIteration:
                continue

            if finding_type.risk_severity is None:
                continue

            severity = finding_type.risk_severity.name.lower()
            total_by_severity[severity] += 1

            if finding.reference not in history_cache:
                history_cache[finding.reference] = self.octopoes_api_connector.get_history(finding.reference)

            if history_cache[finding.reference]:
                first_seen = str(history_cache[finding.reference][0].valid_time)
            else:
                first_seen = "-"

            finding_dict = {"finding": finding, "first_seen": first_seen}

            if finding_type.id in finding_types:
                finding_types[finding_type.id]["occurrences"].append(finding_dict)
            else:
                finding_types[finding_type.id] = {"finding_type": finding_type, "occurrences": [finding_dict]}
                total_by_severity_per_finding_type[severity] += 1

        sorted_finding_types: list[Any] = sorted(
            finding_types.values(), key=lambda x: x["finding_type"].risk_score or 0, reverse=True
        )

        summary = {
            "total_by_severity": total_by_severity,
            "total_by_severity_per_finding_type": total_by_severity_per_finding_type,
            "total_finding_types": len(sorted_finding_types),
            "total_occurrences": sum(total_by_severity.values()),
        }

        return {"finding_types": sorted_finding_types, "summary": summary}
