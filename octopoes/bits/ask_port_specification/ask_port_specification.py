import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.question import Question


def run(input_ooi: Network, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    network = input_ooi

    with (Path(__file__).parent / "question_schema.json").open() as f:
        schema = json.load(f)

    yield Question(ooi=network.reference, schema_id=schema["$id"], json_schema=json.dumps(schema))
