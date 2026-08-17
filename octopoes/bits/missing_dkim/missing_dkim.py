from collections.abc import Iterator
from typing import Any

import tldextract

from octopoes.models import OOI
from octopoes.models.exception import BitNoOperation
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DKIMExists
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: Hostname, additional_oois: list[DKIMExists | NXDOMAIN], config: dict[str, Any]) -> Iterator[OOI]:
    dkim_exists = [ooi for ooi in additional_oois if isinstance(ooi, DKIMExists)]
    nxdomains = (ooi for ooi in additional_oois if isinstance(ooi, NXDOMAIN))

    if any(nxdomains):
        raise BitNoOperation("Related NXDomain found.")

    # only report finding when there is no DKIM record
    if (
        not tldextract.extract(input_ooi.name).subdomain
        and tldextract.extract(input_ooi.name).domain
        and not dkim_exists
    ):
        ft = KATFindingType(id="KAT-NO-DKIM")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description="This hostname does not support DKIM records",
        )
