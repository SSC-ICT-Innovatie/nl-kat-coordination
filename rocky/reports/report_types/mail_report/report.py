from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from reports.report_types.definitions import Report

MAIL_FINDING_TYPES = ["KAT-NO-SPF", "KAT-NO-DMARC", "KAT-NO-DKIM"]


class MailReport(Report):
    id = "mail-report"
    name = _("Mail Report")
    description = _("System specific Mail Report that focusses on IP addresses and hostnames.")
    plugins = {"required": {"dns-records"}, "optional": set()}
    input_ooi_types = {Hostname, IPAddressV4, IPAddressV6}
    template_path = "mail_report/report.html"
    label_style = "2-light"

    def collect_data(self, input_oois: Iterable[Reference], valid_time: datetime) -> dict[Reference, dict[str, Any]]:
        hostnames_by_input_ooi = self.to_hostnames(input_oois, valid_time)
        all_hostnames = list({h for key, hostnames in hostnames_by_input_ooi.items() for h in hostnames})

        filtered_finding_types = self.group_finding_types_by_source(
            self.octopoes_api_connector.query_many("Hostname.<ooi[is Finding].finding_type", valid_time, all_hostnames),
            MAIL_FINDING_TYPES,
        )

        result = {
            ooi: {
                "input_ooi": ooi,
                "finding_types": {},
                "number_of_hostnames": 0,
                "number_of_spf": 0,
                "number_of_dmarc": 0,
                "number_of_dkim": 0,
            }
            for ooi in input_oois
        }

        for input_ooi, hostname_references in hostnames_by_input_ooi.items():
            all_finding_types = []
            number_of_hostnames = len(hostname_references)
            number_of_spf = number_of_hostnames
            number_of_dmarc = number_of_hostnames
            number_of_dkim = number_of_hostnames

            for hostname in hostname_references:
                finding_types = filtered_finding_types.get(hostname, [])

                number_of_spf -= 1 if any(finding.id == "KAT-NO-SPF" for finding in finding_types) else 0
                number_of_dmarc -= 1 if any(finding.id == "KAT-NO-DMARC" for finding in finding_types) else 0
                number_of_dkim -= 1 if any(finding.id == "KAT-NO-DKIM" for finding in finding_types) else 0

                all_finding_types.extend(finding_types)

            result[input_ooi] = {
                "input_ooi": input_ooi,
                "finding_types": all_finding_types,
                "number_of_hostnames": number_of_hostnames,
                "number_of_spf": number_of_spf,
                "number_of_dmarc": number_of_dmarc,
                "number_of_dkim": number_of_dkim,
            }

        return result
