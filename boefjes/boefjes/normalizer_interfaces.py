from boefjes.normalizer_models import NormalizerResults
from boefjes.worker.job_models import NormalizerMeta


class NormalizerJobRunner:
    def run(self, normalizer_meta: NormalizerMeta, raw: bytes) -> NormalizerResults:
        raise NotImplementedError()
