import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    url_reference = Reference.from_str(input_ooi["primary_key"])
    if raw:
        for line in raw.splitlines():
            # Extract and parse values
            data = json.loads(line)
            id_ = data["info"]["classification"]["cve-id"][0].upper()
            description = data["info"]["description"]
            curl_command = data["curl-command"]

            # Create instances of CVEFindingType and Finding classes
            cve_finding_type = CVEFindingType(id=id_)
            yield cve_finding_type

            finding = Finding(
                finding_type=cve_finding_type.reference,
                ooi=url_reference,
                proof=curl_command,
                description=description,
                reproduce=None,  # Set this attribute if you have a reproduce value
            )
            yield finding
