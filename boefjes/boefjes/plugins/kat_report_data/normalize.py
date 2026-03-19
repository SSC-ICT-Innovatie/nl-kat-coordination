from collections.abc import Iterable

from boefjes.normalizer_models import NormalizerDeclaration, NormalizerOutput
from octopoes.models.ooi.reports import ReportData


def run(input_ooi: dict, raw: bytes) -> Iterable[NormalizerOutput]:
    ooi = ReportData.model_validate_json(raw)
    return [NormalizerDeclaration(ooi=ooi)]
