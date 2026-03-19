from boefjes.worker.job_models import NormalizerMeta
from tests.loading import get_dummy_data


def test_no_findings(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("adr-validator-normalize.json"))

    raw = """[{"rule": "TEST-01", "passed": true, "message": ""}]"""
    output = normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    assert len(output.observations) == 1

    observation = output.observations[0]

    assert len(observation.results) == 2

    assert observation.results[0].object_type == "APIDesignRule"
    assert observation.results[0].name == "TEST-01"
    assert observation.results[1].object_type == "APIDesignRuleResult"
    assert observation.results[1].message == ""
    assert observation.results[1].passed is True


def test_with_findings(normalizer_runner):
    meta = NormalizerMeta.model_validate_json(get_dummy_data("adr-validator-normalize.json"))

    raw = """[
        {"rule": "TEST-01", "passed": true, "message": ""},
        {"rule": "TEST-02", "passed": false, "message": "An error"},
        {"rule": "TEST-02", "passed": true, "message": ""}
    ]"""
    output = normalizer_runner.run(meta, bytes(raw, "UTF-8"))

    assert len(output.observations) == 1

    observation = output.observations[0]
    assert len(observation.results) == 8

    assert observation.results[2].object_type == "APIDesignRule"
    assert observation.results[2].name == "TEST-02"
    assert observation.results[3].object_type == "APIDesignRuleResult"
    assert observation.results[3].message == "An error"
    assert observation.results[3].passed is False

    assert observation.results[4].object_type == "ADRFindingType"
    assert observation.results[4].id == "TEST-02"
    assert observation.results[5].object_type == "Finding"
    assert observation.results[5].description == "An error"
    assert str(observation.results[5].finding_type) == "ADRFindingType|TEST-02"
