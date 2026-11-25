from datetime import datetime
from typing import Any

import structlog
from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSRecord
from octopoes.models.ooi.dns.zone import Hostname
from reports.report_types.definitions import Report

logger = structlog.get_logger(__name__)


class DNSReport(Report):
    id = "dns-report"
    name = _("DNS Report")
    description = _("DNS reports focus on domain name system configuration and potential weaknesses.")
    plugins = {"required": {"dns-records", "dns-sec"}, "optional": {"dns-zone"}}
    input_ooi_types = {Hostname}
    template_path = "dns_report/report.html"

    def generate_data(self, input_ooi: str, valid_time: datetime) -> dict[str, Any]:
        ref = Reference.from_str(input_ooi)
        records_tree = self.octopoes_api_connector.get_tree(ref, valid_time, depth=1, types={DNSRecord}).store
        # list_findings_by_ooi collects findings on the hostname and its descendants, with their finding
        # types bundled in; get_tree(types={Finding}) dropped descendant findings after #5088 (see #5202).
        findings_by_ooi = self.octopoes_api_connector.list_findings_by_ooi(ref, valid_time, depth=3)
        finding_types_by_id = {finding_type.id: finding_type for finding_type in findings_by_ooi.finding_types}

        findings = []
        finding_types: dict[str, dict] = {}
        records = []
        security = {"spf": True, "dkim": True, "dmarc": True, "dnssec": True, "caa": True}

        for ooi in findings_by_ooi.findings:
            for check in ["caa", "dkim", "dmarc", "dnssec", "spf"]:
                if f"NO-{check.upper()}" in ooi.finding_type.tokenized.id:
                    security[check] = False
            if ooi.finding_type.tokenized.id == "KAT-INVALID-SPF":
                security["spf"] = False
            if ooi.finding_type.tokenized.id in (
                "KAT-INVALID-SPF",
                "KAT-NAMESERVER-NO-IPV6",
                "KAT-NAMESERVER-NO-TWO-IPV6",
            ):
                findings.append(ooi)
        for ooi_type, ooi in records_tree.items():
            if isinstance(ooi, DNSRecord):
                records.append(
                    {
                        "type": ooi.dns_record_type,
                        "ttl": round(ooi.ttl / 60) if ooi.ttl else "",
                        "name": ooi.hostname.tokenized.name,
                        "content": ooi.value,
                    }
                )

        for finding in findings:
            finding_type = finding_types_by_id.get(finding.finding_type.tokenized.id)
            if finding_type is None:
                logger.error("No Finding Type found for Finding '%s' on date %s.", finding, str(valid_time))
                continue

            if finding_type.id in finding_types:
                finding_types[finding_type.id]["occurrences"].append(finding)
            else:
                finding_types[finding_type.id] = {"finding_type": finding_type, "occurrences": [finding]}

        finding_types_sorted = sorted(
            finding_types.values(), key=lambda x: x["finding_type"].risk_score or 0, reverse=True
        )

        records = sorted(records, key=lambda x: x["type"])

        return {"input_ooi": input_ooi, "records": records, "security": security, "finding_types": finding_types_sorted}
