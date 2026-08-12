import re
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType, RetireJSFindingType, SnykFindingType

CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}")


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ooi = Reference.from_str(input_ooi["primary_key"])
    finding_ids_str = raw.decode()
    finding_ids_list = [fid.strip().upper() for fid in finding_ids_str.split(",")]

    finding_type_mapping = {
        "CVE": CVEFindingType,
        "KAT": KATFindingType,
        "SNYK": SnykFindingType,
        "RETIREJS": RetireJSFindingType,
    }

    for finding_id in finding_ids_list:
        parts = finding_id.split("-")
        prefix = parts[0]

        if prefix in finding_type_mapping:
            if prefix == "CVE" and not CVE_PATTERN.match(finding_id):
                raise ValueError(f"{finding_id} is not a valid CVE ID")

            finding_type = finding_type_mapping[prefix](id=finding_id)
            finding = Finding(
                finding_type=finding_type.reference, ooi=ooi, description=f"{finding_id} is found on this OOI"
            )
            yield finding_type
            yield finding
