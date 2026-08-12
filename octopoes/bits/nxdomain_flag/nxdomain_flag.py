from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: Hostname, additional_oois: list[NXDOMAIN], config: dict[str, Any]) -> Iterator[OOI]:
    if additional_oois:
        nxdomain = KATFindingType(id="KAT-NXDOMAIN")
        yield nxdomain
        yield Finding(
            finding_type=nxdomain.reference, ooi=input_ooi.reference, description="The domain does not exist."
        )
