from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.web import HTTPHeader


def run(input_ooi: HTTPHeader, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    header = input_ooi
    if header.key.lower() != "server":
        return

    if "Apache/2.4.49" in header.value or "Apache/2.4.50" in header.value:
        finding_type = CVEFindingType(id="CVE-2021-41773")
        yield finding_type
        yield Finding(finding_type=finding_type.reference, ooi=header.reference, description="Bad apache version")
