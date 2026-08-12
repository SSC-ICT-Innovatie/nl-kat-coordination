from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HTTPHeaderHostname


def run(
    input_ooi: Hostname, additional_oois: list[NXDOMAIN | HTTPHeaderHostname], config: dict[str, Any]
) -> Iterator[OOI]:
    hostname_exists = True
    headers = []
    for ooi in additional_oois:
        if isinstance(ooi, NXDOMAIN):
            hostname_exists = False
        if isinstance(ooi, HTTPHeaderHostname):
            headers.append(ooi)

    if not hostname_exists:
        ft = KATFindingType(id="KAT-NXDOMAIN-HEADER")
        yield ft
        for header in headers:
            yield Finding(
                ooi=header.reference,
                finding_type=ft.reference,
                description="The hostname in the HTTP header does not exist",
            )
