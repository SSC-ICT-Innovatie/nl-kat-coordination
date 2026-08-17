from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_find_identifiers_in_html(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("body-normalize.json"))
    raw = b"<html><head><script>window.dataLayer=[];</script><!-- GTM-ABC123 --></head></html>"
    output = normalizer_runner.run(meta, raw)
    types = {o.object_type for obs in output.observations for o in obs.results}
    assert {"IdentifierVendor", "Identifier", "IdentifierInstance"} <= types
