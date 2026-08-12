from collections.abc import Iterator
from typing import Any

import tldextract

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DMARCTXTRecord
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: Hostname, additional_oois: list[DMARCTXTRecord | NXDOMAIN], config: dict[str, Any]) -> Iterator[OOI]:
    dmarc_records = [ooi for ooi in additional_oois if isinstance(ooi, DMARCTXTRecord)]
    nxdomains = (ooi for ooi in additional_oois if isinstance(ooi, NXDOMAIN))

    if any(nxdomains):
        return

    # only report finding when there is no DMARC record
    if (
        not tldextract.extract(input_ooi.name).subdomain
        and tldextract.extract(input_ooi.name).domain
        and not dmarc_records
    ):
        ft = KATFindingType(id="KAT-NO-DMARC")
        yield ft
        yield Finding(
            ooi=input_ooi.reference, finding_type=ft.reference, description="This hostname does not have a DMARC record"
        )
