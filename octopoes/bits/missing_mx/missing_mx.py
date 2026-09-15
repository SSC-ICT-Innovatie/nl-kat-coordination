from collections.abc import Iterator
from typing import Any

import tldextract

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType

# RFC 7505: a null MX record has value "." and preference 0, meaning the domain
# explicitly does not accept mail. We should not flag such domains.
NULL_MX_VALUE = "."


def run(input_ooi: Hostname, additional_oois: list[DNSMXRecord | NXDOMAIN], config: dict[str, Any]) -> Iterator[OOI]:
    """Flag domains (not subdomains) that have no MX records.

    Follows the same pattern as missing-spf: only checks apex domains using tldextract,
    and skips NXDOMAIN hostnames. A null MX (RFC 7505, value ".") counts as a valid
    MX record — the domain explicitly opts out of email.
    """
    mx_records = [ooi for ooi in additional_oois if isinstance(ooi, DNSMXRecord)]
    nxdomains = [ooi for ooi in additional_oois if isinstance(ooi, NXDOMAIN)]

    if nxdomains:
        return

    # Only check domains (no subdomain), same as missing-spf
    if tldextract.extract(input_ooi.name).subdomain or not tldextract.extract(input_ooi.name).domain:
        return

    # A null MX record (RFC 7505) is a valid way to say "no email here"
    has_mx = any(mx.value.strip() != NULL_MX_VALUE for mx in mx_records)
    has_null_mx = any(mx.value.strip() == NULL_MX_VALUE for mx in mx_records)

    if not has_mx and not has_null_mx:
        ft = KATFindingType(id="KAT-NO-MX")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description="This domain does not have an MX record and does not declare a null MX (RFC 7505).",
        )
