"""Interpret drill -DT output without attributing unrelated records to the input hostname."""

import re
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType

STATUS = re.compile(r"^\[([USTB])\]\s+(\S+)\s+\d+\s+IN\s+(A|AAAA|CNAME)\s+", re.I)

# Signed or unsigned "no such record" answers for the name itself, e.g.
# "[T] Existence denied: nl. A" or "[U] No data found for: example.org. type A".
NO_DATA = re.compile(
    r"^\[([USTB])\]\s+(?:Existence denied:|No data found for:)\s+(\S+)\s+(?:type\s+)?(A|AAAA|CNAME)\b", re.I
)


def canonical(name: str) -> str:
    return name.rstrip(".").lower()


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    result = raw.decode("utf-8", errors="replace")
    ooi_ref = Reference.from_str(input_ooi["primary_key"])
    domain = canonical(input_ooi["name"])

    # Match answer record owners, not drill traversal section headers.
    # DNSKEY/DS records and unrelated CNAME targets must not determine the finding.
    candidates = []
    for line in result.splitlines():
        match = STATUS.match(line) or NO_DATA.match(line)
        if match and canonical(match.group(2)) == domain:
            candidates.append((match.group(1).upper(), match.group(3).upper(), line))

    if not candidates:
        raise ValueError(f"No DNSSEC answer status for {domain} in drill output")
    # In case of multiple answers, report a validation failure rather than hiding it.
    states = {status for status, _, _ in candidates}
    if "B" in states:
        finding_id = "KAT-INVALID-DNSSEC"
        reason = "DNSSEC validation failed (bogus answer)"
    elif "S" in states:
        # drill -T marks an answer [S] when it is signed but cannot be chained to the trust
        # anchor, e.g. a DS at the parent that matches no DNSKEY (dnssec-failed.org).
        finding_id = "KAT-INVALID-DNSSEC"
        reason = "DNSSEC answer is signed but not authenticated by the chain of trust"
    elif "U" in states:
        finding_id = "KAT-NO-DNSSEC"
        reason = "DNS answer is unsigned or has no authenticated chain of trust"
    else:
        return

    ft = KATFindingType(id=finding_id)
    record_types = ", ".join(sorted({kind for _, kind, _ in candidates}))
    finding = Finding(finding_type=ft.reference, ooi=ooi_ref, description=f"{reason} for {domain} ({record_types}).")
    yield ft
    yield finding
