import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerDeclaration, NormalizerOutput


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    for declaration in json.loads(raw.decode()):
        end_valid_time = declaration.pop("end_valid_time", None)
        yield NormalizerDeclaration(ooi=declaration["ooi"], end_valid_time=end_valid_time)
