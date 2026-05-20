from collections.abc import Iterator
from typing import Any

from octopoes.models import OOI
from octopoes.models.exception import BitNoOperation
from octopoes.models.ooi.findings import Finding, KATFindingType
from octopoes.models.ooi.web import HostnameHTTPURL, HTTPHeader


def run(input_ooi: HostnameHTTPURL, additional_oois: list[HTTPHeader], config: dict[str, Any]) -> Iterator[OOI]:
    header_keys = [header.key.lower() for header in additional_oois if isinstance(header, HTTPHeader)]

    # only check for http urls
    if input_ooi.scheme.value == "https" or not header_keys:
        raise BitNoOperation("Already https")

    if "location" not in header_keys:
        ft = KATFindingType(id="KAT-NO-HTTPS-REDIRECT")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description="This HTTP URL may not redirect to HTTPS; 'location' was not found in HTTPHeader.",
        )
