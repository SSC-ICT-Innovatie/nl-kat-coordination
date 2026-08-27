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
    meta = NormalizerMeta.model_validate_json(get_dummy_data("body-identifier.json"))
    raw = b"""<html><head><script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-12345');</script></head></html>"""
    output = normalizer_runner.run(meta, raw)
    types = {o.object_type for obs in output.observations for o in obs.results}
    assert {"IdentifierVendor", "Identifier", "IdentifierInstance"} <= types


def test_mapbox_pattern_ignores_bundler_filenames_but_matches_tokens():
    # Bundled assets like chunk-vendors.abc123.pk.min.js must not mint a fake
    # Mapbox identifier; real Mapbox tokens always start with "pk.eyJ".
    raw = b'<script src="/assets/chunk-vendors.abc123.pk.min.js"></script>'
    assert extract_identifiers(raw.decode()) == set()

    token = "pk.eyJub3QiOiJhLXJlYWwtdG9rZW4ifQ.dummy-signature-for-tests"  # fake, matches the pk.eyJ shape
    matches = extract_identifiers(f'<script>mapboxgl.accessToken = "{token}";</script>')
    assert matches == {IdentifierMatch(vendor="Mapbox", identifier=token)}


def test_sentry_capture_does_not_span_lines():
    # One @sentry.io occurrence must not reach back across newlines to an
    # unrelated earlier URL and swallow everything in between.
    text = 'src="https://cdn.example.com/app.js"\nvar dsn = "https://abc123@sentry.io/42";'
    matches = extract_identifiers(text)
    assert matches == {IdentifierMatch(vendor="Sentry", identifier="abc123@sentry.io/42")}


def test_pipe_in_capture_value_is_not_matched():
    # A pipe is the OOI reference separator; a value containing one must not
    # become an Identifier (natural-key safety).
    assert extract_identifiers('analytics.load("foo|bar")') == set()
    assert extract_identifiers('"projectId": "my|project"') == set()
