from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(hostname: Hostname, additional_oois: list[DNSTXTRecord], config: dict[str, Any]) -> Iterator[OOI]:
    # https://www.rfc-editor.org/info/rfc7208/#section-3.2
    spf_records = [
        spf_record
        for spf_record in additional_oois
        if spf_record.value.lower().startswith("v=spf1 ") or spf_record.value.lower() == "v=spf1"
    ]

    if len(spf_records) > 1:
        finding_type = KATFindingType(id="KAT-MULTIPLE-SPF-RECORDS")
        yield finding_type
        yield Finding(
            finding_type=finding_type.reference,
            ooi=hostname.reference,
            description="This host has multiple spf records, only one can exist.",
        )
