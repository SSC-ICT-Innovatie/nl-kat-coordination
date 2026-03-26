import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models.ooi.findings import CWEFindingType, RiskLevelSeverity

logger = logging.getLogger(__name__)


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    cwe_finding_type_id = input_ooi["id"]
    data = json.loads(raw)

    risk_severity = RiskLevelSeverity.UNKNOWN
    risk_score = None

    yield NormalizerAffirmation(
        ooi=CWEFindingType(
            id=cwe_finding_type_id,
            description=f"{data['name']} - {data['description']}",
            source=f'https://cwe.mitre.org/data/definitions/{cwe_finding_type_id.split("-")[1]}.html',
            risk_severity=risk_severity,
            risk_score=risk_score,
        )
    )
