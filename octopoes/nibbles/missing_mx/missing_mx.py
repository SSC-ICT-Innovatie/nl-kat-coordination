from collections.abc import Iterator

import tldextract

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType


def nibble(hostname: Hostname, mx_record: DNSMXRecord | None, nx_domain: NXDOMAIN | None) -> Iterator[OOI]:
    if nx_domain:
        return
    # only report finding when there is no MX record
    if not tldextract.extract(hostname.name).subdomain and tldextract.extract(hostname.name).domain and not mx_record:
        ft = KATFindingType(id="KAT-NO-MX")
        yield ft
        yield Finding(
            ooi=hostname.reference, finding_type=ft.reference, description="This hostname does not have an MX record"
        )
