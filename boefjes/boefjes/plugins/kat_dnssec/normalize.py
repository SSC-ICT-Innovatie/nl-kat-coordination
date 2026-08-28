from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    result = raw.decode()

    ooi_ref = Reference.from_str(input_ooi["primary_key"])

    # We are looking for the last line that isn't a comment (doesn't start with
    # ";"), so we reverse the output lines before looping over them.
    for result_line in reversed(result.splitlines()):
        if not result_line.startswith(";"):
            break

    # [S] self sig OK; [B] bogus; [T] trusted; [U] unsigned
    if result_line.startswith("[U]"):
        if f"No DS record found for {ooi_ref.human_readable}., but valid CNAME" in result:
            # hostname is a cname to another point, drill does not follow the cname.
            return
        ft = KATFindingType(id="KAT-NO-DNSSEC")
        finding = Finding(
            finding_type=ft.reference,
            ooi=ooi_ref,
            description=f"Domain {ooi_ref.human_readable} is not signed with DNSSEC.",
        )
        yield ft
        yield finding
    elif result_line.startswith("[S]") or result_line.startswith("[B]"):
        ft = KATFindingType(id="KAT-INVALID-DNSSEC")
        finding = Finding(
            finding_type=ft.reference,
            ooi=ooi_ref,
            description=f"Domain {ooi_ref.human_readable} is signed with an invalid DNSSEC.",
        )
        yield ft
        yield finding
    elif not result_line.startswith("[T]"):
        raise ValueError(f"Could not parse drill output: {result_line}")
