import json

from bits.ask_csp_policy.ask_csp_policy import run

from octopoes.models.ooi.network import Network
from octopoes.models.ooi.question import Question


def test_ask_csp_policy_yields_question_for_check_csp_policy_config():
    results = list(run(Network(name="internet"), [], {}))

    assert len(results) == 1
    question = results[0]
    assert isinstance(question, Question)
    # The Config created from the answer takes its bit_id from the last schema id segment,
    # so it must name the consuming bit exactly.
    assert question.schema_id == "/bit/check-csp-policy"

    schema = json.loads(question.json_schema)
    assert set(schema["properties"]) == {
        "required_directives",
        "deprecated_directives",
        "forbidden_keywords",
        "allowed_hosts",
    }
