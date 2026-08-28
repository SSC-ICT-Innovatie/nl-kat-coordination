from collections.abc import Iterator

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeaderHostname


def nibble(http_header_hostname: HTTPHeaderHostname, _: NXDOMAIN) -> Iterator[OOI]:
    ft = KATFindingType(id="KAT-NXDOMAIN-HEADER")
    yield ft
    yield Finding(
        ooi=http_header_hostname.reference,
        finding_type=ft.reference,
        description="The hostname in the HTTP header does not exist",
    )
