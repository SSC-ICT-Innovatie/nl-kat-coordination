from collections.abc import Iterable

import structlog

from boefjes.normalizer_interfaces import NormalizerJobRunner
from boefjes.normalizer_models import (
    NormalizerAffirmation,
    NormalizerDeclaration,
    NormalizerObservation,
    NormalizerOutput,
    NormalizerResults,
)
from boefjes.worker.interfaces import JobRuntimeError
from boefjes.worker.job_models import InvalidReturnValueNormalizer, NormalizerMeta, ObservationsWithoutInputOOI
from boefjes.worker.repository import LocalPluginRepository
from octopoes.models import OOI, DeclaredScanProfile

logger = structlog.get_logger(__name__)


class LocalNormalizerJobRunner(NormalizerJobRunner):
    def __init__(self, local_repository: LocalPluginRepository):
        self.local_repository = local_repository

    def run(self, normalizer_meta: NormalizerMeta, raw: bytes) -> NormalizerResults:
        logger.debug("Running local normalizer plugin")

        normalizers = self.local_repository.resolve_normalizers()
        normalizer = normalizers[normalizer_meta.normalizer.id]

        try:
            try:
                input_ooi = normalizer_meta.raw_data.boefje_meta.arguments["input"]
            except KeyError:
                if normalizer_meta.raw_data.boefje_meta.input_ooi:
                    input_ooi = {"primary_key": normalizer_meta.raw_data.boefje_meta.input_ooi}
                else:
                    input_ooi = {}

            results = normalizer.module.run(input_ooi, raw)
        except BaseException as e:
            raise JobRuntimeError("Normalizer failed") from e

        return self._parse_results(normalizer_meta, results)

    def _parse_results(self, normalizer_meta: NormalizerMeta, results: Iterable[NormalizerOutput]) -> NormalizerResults:
        oois = []
        declarations = []
        affirmations = []
        scan_profiles = []

        for result in results:
            match result:
                case OOI():
                    oois.append(result)
                case NormalizerDeclaration():
                    declarations.append(result)
                case NormalizerAffirmation():
                    affirmations.append(result)
                case DeclaredScanProfile():
                    scan_profiles.append(result)
                case _:
                    raise InvalidReturnValueNormalizer(
                        f"Normalizer returned object of incorrect type: {result.__class__.__name__}"
                    )

        if oois:
            if not normalizer_meta.raw_data.boefje_meta.input_ooi:
                raise ObservationsWithoutInputOOI(normalizer_meta)

            observations = [
                NormalizerObservation(
                    type="observation", input_ooi=normalizer_meta.raw_data.boefje_meta.input_ooi, results=oois
                )
            ]
        else:
            observations = []

        return NormalizerResults(
            observations=observations, declarations=declarations, affirmations=affirmations, scan_profiles=scan_profiles
        )
