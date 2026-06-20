import io
import logging
from collections.abc import Iterable

import yaml

from boefjes.normalizer_models import NormalizerDeclaration, NormalizerOutput

logger = logging.getLogger(__name__)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    yield from process_yml(raw)


def process_yml(yml_raw_data: bytes) -> Iterable[NormalizerOutput]:
    yml_data = io.StringIO(yml_raw_data.decode())
    oois_from_yaml = yaml.safe_load(yml_data)
    oois: list[NormalizerOutput] = []
    for ooi in oois_from_yaml.get("oois"):
        oois.append(NormalizerDeclaration(ooi=ooi))
    return oois
