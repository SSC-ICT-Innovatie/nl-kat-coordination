import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models.ooi.findings import KATFindingType, RiskLevelSeverity

logger = logging.getLogger(__name__)


SEVERITY_SCORE_LOOKUP = {
    RiskLevelSeverity.CRITICAL: 10.0,
    RiskLevelSeverity.HIGH: 8.9,
    RiskLevelSeverity.MEDIUM: 6.9,
    RiskLevelSeverity.LOW: 3.9,
    RiskLevelSeverity.RECOMMENDATION: 0.0,
}


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    kat_finding_type_id = input_ooi["id"]
    data = json.loads(raw)

    finding_type_information = data[kat_finding_type_id]
    risk_severity = RiskLevelSeverity(finding_type_information["risk"].lower())

    risk_score = SEVERITY_SCORE_LOOKUP[risk_severity]

    yield NormalizerAffirmation(
        ooi=KATFindingType(
            id=kat_finding_type_id,
            name=finding_type_information.get("name", None),
            description=finding_type_information.get("description", None),
            source=finding_type_information.get("source", None),
            impact=finding_type_information.get("impact", None),
            recommendation=finding_type_information.get("recommendation", None),
            risk_severity=risk_severity,
            risk_score=risk_score,
        )
    )
