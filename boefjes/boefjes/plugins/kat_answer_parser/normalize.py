import json
from collections.abc import Iterable

import structlog

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models.ooi.config import Config

logger = structlog.get_logger(__name__)

REQUIRED_KEYS = ("schema", "answer_ooi", "answer")


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        logger.warning("kat_answer_parser: missing keys %s in raw data", missing)
        return

    bit_id = data["schema"].removeprefix("/bit/")

    yield Config(ooi=data["answer_ooi"], bit_id=bit_id, config=data["answer"])
