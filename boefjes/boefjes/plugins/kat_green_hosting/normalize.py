import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw.decode())

    website_reference = Reference.from_str(input_ooi["primary_key"])

    if not data["green"]:
        ft = KATFindingType(id="KAT-NO-GREEN-HOSTING")
        yield ft
        yield Finding(
            finding_type=ft.reference,
            ooi=website_reference,
            description="This server is not running in a 'green' datacenter according to the Green Web Foundation.",
        )
