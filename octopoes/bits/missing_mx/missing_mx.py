from collections.abc import Iterator
from typing import Any

import tldextract

from octopoes.models import OOI
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding, KATFindingType

# RFC 7505: a null MX record has preference 0 and target ".", meaning the domain
# explicitly does not accept mail. We should not flag such domains.
# The DNS normalizer stores the value as "preference target" (e.g. "0 ."), so we
# check whether the target part (after the first space) is ".".
NULL_MX_TARGET = "."


def _is_null_mx(mx: DNSMXRecord) -> bool:
    """Check whether an MX record is a null MX (RFC 7505).

    The DNS normalizer stores the value as "preference target" (e.g. "0 ."),
    so we check whether the target part (after the first space) is ".".
    """
    parts = mx.value.strip().split(None, 1)
    return len(parts) == 2 and parts[1].strip() == NULL_MX_TARGET


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
    has_mx = any(not _is_null_mx(mx) for mx in mx_records)
    has_null_mx = any(_is_null_mx(mx) for mx in mx_records)

    if not has_mx and not has_null_mx:
        ft = KATFindingType(id="KAT-NO-MX")
        yield ft
        yield Finding(
            ooi=input_ooi.reference,
            finding_type=ft.reference,
            description="This domain does not have an MX record and does not declare a null MX (RFC 7505).",
        )
