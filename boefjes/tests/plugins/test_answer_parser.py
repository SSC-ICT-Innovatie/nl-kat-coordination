import pytest
from pydantic import ValidationError

from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_config_yielded(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("answer-normalize.json"))

    with pytest.raises(TypeError):
        raw = '[{"key": "test"}]'
        normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    with pytest.raises(ValidationError):
        raw = '{"schema": "/bit/port-classification-ip", "answer": [{"key": "test"}], "answer_ooi": "Network|internet"}'
        normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    raw = '{"schema": "/bit/port-classification-ip", "answer": {"key": "test"}, "answer_ooi": "Network|internet"}'
    output = normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    assert len(output.observations) == 1
    assert len(output.observations[0].results) == 1
    assert output.observations[0].results[0].object_type == "Config"
