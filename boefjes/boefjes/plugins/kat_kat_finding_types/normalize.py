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

    finding_type_information = data.get(kat_finding_type_id)
    if finding_type_information is None:
        # The static catalog does not (yet) describe this finding type. Affirm it
        # with unknown severity so the finding still hydrates, instead of raising
        # KeyError and failing hydration for every finding of this type. Ids
        # minted by bits (e.g. KAT-HTTPS-NOT-AVAILABLE) can be absent from the
        # catalog and used to hit this path.
        logger.warning("Unknown KAT finding type id %s, affirming with unknown severity.", kat_finding_type_id)
        yield NormalizerAffirmation(
            ooi=KATFindingType(id=kat_finding_type_id, risk_severity=RiskLevelSeverity.UNKNOWN, risk_score=None)
        )
        return

    risk = finding_type_information.get("risk")
    try:
        risk_severity = RiskLevelSeverity(str(risk).lower()) if risk else RiskLevelSeverity.UNKNOWN
    except ValueError:
        logger.warning("Unknown risk level %r for KAT finding type %s.", risk, kat_finding_type_id)
        risk_severity = RiskLevelSeverity.UNKNOWN

    risk_score = SEVERITY_SCORE_LOOKUP.get(risk_severity)

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
