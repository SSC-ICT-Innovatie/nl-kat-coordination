import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.geography import GeographicPoint


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    """Yields GeographicPoints."""
    results = json.loads(raw)
    if not results:
        return

    yield GeographicPoint(
        ooi=Reference.from_str(input_ooi["primary_key"]),
        longitude=results.get("location", {}).get("longitude"),
        latitude=results.get("location", {}).get("latitude"),
    )
