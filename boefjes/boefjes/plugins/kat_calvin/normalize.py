import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerDeclaration, NormalizerOutput
from octopoes.models.ooi.monitoring import Application, Incident


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    data = json.loads(raw)

    for log in data:
        yield from parse_log(log)


def parse_log(log: dict) -> Iterable[NormalizerOutput]:
    app = Application(name=log.pop("client_environment_app"))

    yield NormalizerDeclaration(ooi=app)

    mandatory_fields = {
        "event_id": str(log.pop("eventId")),
        "severity": log.pop("severity"),
        "event_title": log.pop("eventTitle"),
        "event_type": log.pop("eventType"),
    }

    yield NormalizerDeclaration(ooi=Incident(application=app.reference, **mandatory_fields, meta_data=log))
