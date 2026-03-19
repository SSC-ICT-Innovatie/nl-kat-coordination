import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models.ooi.findings import RiskLevelSeverity, SnykFindingType

logger = logging.getLogger(__name__)


SEVERITY_SCORE_LOOKUP = {
    RiskLevelSeverity.CRITICAL: 9.0,
    RiskLevelSeverity.HIGH: 7.0,
    RiskLevelSeverity.MEDIUM: 4.0,
    RiskLevelSeverity.LOW: 0.1,
    RiskLevelSeverity.RECOMMENDATION: 0.0,
}


def get_risk_level(severity_score):
    for risk_level, score in SEVERITY_SCORE_LOOKUP.items():
        if severity_score >= score:
            return risk_level
    return None


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    snyk_finding_type_id = input_ooi["id"]
    data = json.loads(raw)

    risk_score = data.get("risk")
    risk_severity = get_risk_level(float(risk_score))

    yield NormalizerAffirmation(
        ooi=SnykFindingType(
            id=snyk_finding_type_id,
            description=data.get("summary"),
            source=f"https://snyk.io/vuln/{snyk_finding_type_id}",
            risk_severity=risk_severity,
            risk_score=risk_score,
        )
    )
