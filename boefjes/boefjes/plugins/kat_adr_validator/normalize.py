import json
from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerOutput
from octopoes.models import Reference
from octopoes.models.ooi.findings import ADRFindingType, Finding
from octopoes.models.ooi.web import APIDesignRule, APIDesignRuleResult


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ooi_ref = Reference.from_str(input_ooi["primary_key"])

    results = json.loads(raw)

    for result in results:
        rule_name = result["rule"]
        passed = result["passed"]
        message = result["message"]

        rule = APIDesignRule(name=rule_name)
        rule_result = APIDesignRuleResult(rest_api=ooi_ref, rule=rule.reference, passed=passed, message=message)

        yield rule
        yield rule_result

        if passed:
            continue

        ft = ADRFindingType(id=rule_name)
        finding = Finding(finding_type=ft.reference, ooi=ooi_ref, description=message)

        yield ft
        yield finding
