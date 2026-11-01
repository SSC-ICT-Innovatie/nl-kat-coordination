from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_page_analyzer_normalizer(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("body-page-analysis-normalize.json"))
    output = normalizer_runner.run(meta, get_dummy_data("download_page_analysis.raw"))

    assert output.observations
    results = output.observations[0].results
    assert len(results) == 14
    assert {o.primary_key for o in results if o.object_type == "Software"} == {
        "Software|BootstrapCDN|3.3.7|",
        "Software|Bootstrap|3.3.7|cpe:2.3:a:getbootstrap:3.3.7:*:*:*:*:*:*:*:*",
        "Software|cdnjs||",
        "Software|jQuery Migrate|1.0.0|",
        "Software|jQuery|3.6.0|cpe:2.3:a:jquery:3.6.0:*:*:*:*:*:*:*:*",
        "Software|jQuery||cpe:2.3:a:jquery:jquery:*:*:*:*:*:*:*:*",
    }


def test_normalizer_handles_html_content_type_without_body(normalizer_runner):
    # Regression: a response with Content-Type: text/html but an empty body
    # (redirect / Content-Length: 0) must not crash the normalizer. har.html raises
    # ValueError("No HTML content found") inside analyze_html/analyze_dom/analyze_meta/
    # analyze_script_src_in_html, so all four must be skipped when there is no body.
    meta = NormalizerMeta.model_validate_json(get_dummy_data("body-page-analysis-normalize.json"))

    # Must complete without raising.
    output = normalizer_runner.run(meta, get_dummy_data("empty-html-body.raw"))

    results = [r for obs in output.observations for r in obs.results]
    assert not any(o.object_type == "Software" for o in results)
