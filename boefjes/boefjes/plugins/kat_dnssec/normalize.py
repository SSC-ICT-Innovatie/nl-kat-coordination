from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    result = raw.decode()

    ooi_ref = Reference.from_str(input_ooi["primary_key"])
    domain = input_ooi["name"]

    # Find the status line for the queried domain, not just the last status line
    # in the output. A drill trace may end at a CNAME/AAAA target that is
    # unsigned ([U]) even though the queried domain itself is signed ([T]).
    # The relevant status line is the one on the answer record for the domain.
    status_line = None
    in_domain_section = False
    for result_line in result.splitlines():
        if result_line.startswith(f";; Domain: {domain}"):
            in_domain_section = True
            continue
        if in_domain_section and result_line.startswith(("[U]", "[S]", "[B]", "[T]")):
            status_line = result_line
            break

    # Fall back to the last status line if we didn't find the domain section
    if status_line is None:
        for result_line in reversed(result.splitlines()):
            if result_line.startswith(("[U]", "[S]", "[B]", "[T]")):
                status_line = result_line
                break
        else:
            raise ValueError("No status line found in drill output")

    # [S] self sig OK; [B] bogus; [T] trusted; [U] unsigned
    if status_line.startswith("[U]"):
        ft = KATFindingType(id="KAT-NO-DNSSEC")
        finding = Finding(
            finding_type=ft.reference,
            ooi=ooi_ref,
            description=f"Domain {ooi_ref.human_readable} is not signed with DNSSEC.",
        )
        yield ft
        yield finding
    elif status_line.startswith("[S]") or status_line.startswith("[B]"):
        ft = KATFindingType(id="KAT-INVALID-DNSSEC")
        finding = Finding(
            finding_type=ft.reference,
            ooi=ooi_ref,
            description=f"Domain {ooi_ref.human_readable} is signed with an invalid DNSSEC.",
        )
        yield ft
        yield finding
