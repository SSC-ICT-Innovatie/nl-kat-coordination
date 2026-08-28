import json
import logging
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerAffirmation, NormalizerOutput
from octopoes.models.ooi.findings import CVEFindingType, RiskLevelSeverity

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
    cve_finding_type_id = input_ooi["id"]
    data = json.loads(raw)

    descriptions = data["cve"]["descriptions"]
    english_description = [description for description in descriptions if description["lang"] == "en"][0]

    if not data["cve"]["metrics"]:
        risk_severity = RiskLevelSeverity.UNKNOWN
        risk_score = None
    else:
        metrics = data["cve"]["metrics"]
        # NVD may return only a CVSS v4.0 metric (or a version we do not parse).
        # The old code fell through to metrics["cvssMetricV2"], raising KeyError
        # in that case, which aborts the normalizer and drops the finding type.
        # Prefer the known metric versions and fall back to UNKNOWN instead.
        # v4.0 deliberately comes after v3.x: the severity bands in
        # get_risk_level were drawn for v3.x scores, so preferring v3.x keeps
        # scores comparable with historical data. Empty metric lists are
        # skipped so a populated later version wins over an empty earlier one.
        for metric in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40", "cvssMetricV2"):
            if metrics.get(metric):
                cvss = metrics[metric]
                break
        else:
            cvss = None

        if not cvss:
            risk_severity = RiskLevelSeverity.UNKNOWN
            risk_score = None
        else:
            primary = next((item for item in cvss if item["type"] == "Primary"), cvss[0])
            risk_score = primary.get("cvssData", {}).get("baseScore")
            risk_severity = get_risk_level(risk_score) if risk_score is not None else RiskLevelSeverity.UNKNOWN

    yield NormalizerAffirmation(
        ooi=CVEFindingType(
            id=cve_finding_type_id,
            description=english_description["value"],
            source=f"https://cve.circl.lu/cve/{cve_finding_type_id}",
            risk_severity=risk_severity,
            risk_score=risk_score,
        )
    )
