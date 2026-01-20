import json
from collections.abc import Iterable
from typing import Any

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def scan_octoscan_output(data: list[dict[str, Any]], ooi_ref: Reference) -> Iterable[NormalizerOutput]:
    if data:
        finding_type = KATFindingType(id="KAT-VULNERABLE-GH-WORKFLOW")
        yield finding_type

    description = "Found vulnerabilities in GitHub workflow files.\n"

    for vuln in data:
        description += f"{vuln['message']}\nInside file {vuln['filepath']} on line {vuln['line']}\n\n"

    yield Finding(finding_type=finding_type.reference, ooi=ooi_ref, description=description)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    ooi_ref = Reference.from_str(input_ooi["primary_key"])

    yield from scan_octoscan_output(data, ooi_ref)
