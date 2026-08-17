from boefjes.plugins.kat_webpage_analysis.find_identifiers_in_html.normalize import IdentifierMatch, extract_identifiers
from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_extract_identifiers():
    raw = b"""<html><head><script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-12345');</script></head></html>"""

    assert extract_identifiers(raw.decode()) == {IdentifierMatch(vendor="GoogleTagManager", identifier="GTM-12345")}


def test_find_identifiers_in_html(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("body-normalize.json"))
    raw = b"""<html><head><script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-12345');</script></head></html>"""
    output = normalizer_runner.run(meta, raw)
    types = {o.object_type for obs in output.observations for o in obs.results}
    assert {"IdentifierVendor", "Identifier", "IdentifierInstance"} <= types
