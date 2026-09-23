import pytest
from pydantic import ValidationError

from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_config_yielded(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("answer-normalize.json"))

    # Malformed raw (a list instead of a dict) fails the task rather than
    # returning no objects, which would GC the previously yielded Config (#3958)
    with pytest.raises(ValueError, match="expected a JSON object"):
        normalizer_runner.run(meta, bytes('[{"key": "test"}]', "UTF-8"))

    # Missing keys likewise fail with a clear message instead of an opaque KeyError
    with pytest.raises(ValueError, match="missing keys"):
        normalizer_runner.run(meta, bytes('{"schema": "/bit/port-classification-ip"}', "UTF-8"))

    with pytest.raises(ValidationError):
        raw = '{"schema": "/bit/port-classification-ip", "answer": [{"key": "test"}], "answer_ooi": "Network|internet"}'
        normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    raw = '{"schema": "/bit/port-classification-ip", "answer": {"key": "test"}, "answer_ooi": "Network|internet"}'
    output = normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    assert len(output.observations) == 1
    assert len(output.observations[0].results) == 1
    assert output.observations[0].results[0].object_type == "Config"
