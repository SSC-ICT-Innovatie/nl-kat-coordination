import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    url_reference = Reference.from_str(input_ooi["primary_key"])
    if raw:
        for line in raw.splitlines():
            # Extract and parse values
            data = json.loads(line)
            description = data["info"]["description"]
            curl_command = data["curl-command"]

            # Create instances of CVEFindingType and Finding classes
            kft = KATFindingType(id="EXPOSED-PANELS")
            yield kft

            finding = Finding(
                finding_type=kft.reference,
                ooi=url_reference,
                proof=curl_command,
                description=description,
                reproduce=None,  # Set this attribute if you have a reproduce value
            )
            yield finding
