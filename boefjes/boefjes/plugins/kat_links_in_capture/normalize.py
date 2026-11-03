from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from boefjes.plugins.kat_links_in_capture.links import hostname_oois


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    yield from hostname_oois(input_ooi, raw, external=False)
