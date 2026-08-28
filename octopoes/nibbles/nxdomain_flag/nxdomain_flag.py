from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.findings import Finding, KATFindingType


def nibble(nxdomain: NXDOMAIN) -> Iterator[OOI]:
    ft = KATFindingType(id="KAT-NXDOMAIN")
    yield ft
    yield Finding(finding_type=ft.reference, ooi=nxdomain.hostname, description="The domain does not exist.")
