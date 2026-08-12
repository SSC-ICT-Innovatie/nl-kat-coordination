import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.web import HTTPHeader


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    # fetch a reference to the original resource where these headers where downloaded from
    resource = Reference.from_str(input_ooi["primary_key"])

    for key, value in json.loads(raw).items():
        yield HTTPHeader(resource=resource, key=key, value=value)
