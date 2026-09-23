import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.config import Config

REQUIRED_KEYS = ("schema", "answer_ooi", "answer")


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    # A malformed raw must fail the task, not return no objects: an empty result
    # tells Octopoes to drop the previously yielded Config OOI and GC it.
    if not isinstance(data, dict):
        raise ValueError(f"kat_answer_parser: expected a JSON object, got {type(data).__name__}")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"kat_answer_parser: missing keys {missing} in raw data")

    bit_id = data["schema"].removeprefix("/bit/")

    yield Config(ooi=data["answer_ooi"], bit_id=bit_id, config=data["answer"])
