from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(hostname: Hostname, additional_oois: list[DNSTXTRecord], config: dict[str, Any]) -> Iterator[OOI]:
    csp_records = [csp_record for csp_record in additional_oois if csp_record.value.startswith("v=spf1 ")]

    if len(csp_records) > 1:
        finding_type = KATFindingType(id="KAT-MULTIPLE-CSP")
        yield finding_type
        yield Finding(
            finding_type=finding_type.reference,
            ooi=hostname.reference,
            description="This host has multiple CSP records, only one can exist.",
        )
