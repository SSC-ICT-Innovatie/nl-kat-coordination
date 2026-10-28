"""Tests for optional, database-level Finding Type classification filters."""

from datetime import UTC, datetime
from unittest.mock import Mock

from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models.ooi.findings import RiskLevelSeverity
from octopoes.repositories.ooi_repository import XTDBOOIRepository


def test_filtered_count_and_page_use_same_classification_clauses():
    session = Mock()
    session.client.query.return_value = [[2]]
    repository = XTDBOOIRepository(Mock(), session)
    repository.query = Mock(return_value=[("finding", 8.0, "finding_type")])
    when = datetime.now(UTC)
    options = {
        "group": "web-security",
        "tag": "misconfiguration",
        "search_string": "example",
        "exclude_muted": True,
        "order_by": "score",
        "asc_desc": "desc",
    }

    result = repository.list_findings({RiskLevelSeverity.HIGH}, when, limit=1, **options)

    assert result.count == 2
    assert result.items == ["finding"]
    finding_query = repository.query.call_args.args[0]
    count_query = session.client.query.call_args.args[0]
    for query in (finding_query, count_query):
        assert '[?finding_type :KATFindingType/groups "web-security"]' in query
        assert '[?finding_type :KATFindingType/tags "misconfiguration"]' in query
        assert "(not-join [?finding]" in query
        assert "example" in query
        assert '"high"' in query
    assert ":limit 1" in finding_query
    assert ":offset 0" in finding_query
    assert ":limit 1" not in count_query


def test_count_only_applies_classification_filters():
    session = Mock()
    session.client.query.return_value = [[3]]
    repository = XTDBOOIRepository(Mock(), session)

    result = repository.list_findings({RiskLevelSeverity.MEDIUM}, datetime.now(UTC), limit=0, tag="misconfiguration")

    assert result.count == 3
    assert result.items == []
    query = session.client.query.call_args.args[0]
    assert '[?finding_type :KATFindingType/tags "misconfiguration"]' in query
    assert ":KATFindingType/groups" not in query


def test_unfiltered_query_does_not_require_classification():
    session = Mock()
    session.client.query.return_value = [[4]]
    repository = XTDBOOIRepository(Mock(), session)

    result = repository.list_findings({RiskLevelSeverity.HIGH}, datetime.now(UTC), limit=0)

    assert result.count == 4
    query = session.client.query.call_args.args[0]
    assert ":KATFindingType/groups" not in query
    assert ":KATFindingType/tags" not in query


def test_classification_values_are_escaped_in_query():
    session = Mock()
    session.client.query.return_value = [[0]]
    repository = XTDBOOIRepository(Mock(), session)

    repository.list_findings({RiskLevelSeverity.HIGH}, datetime.now(UTC), limit=0, group='odd"\\value')

    query = session.client.query.call_args.args[0]
    assert '[?finding_type :KATFindingType/groups "odd\\"\\\\value"]' in query


def test_connector_sends_optional_classification_parameters():
    connector = object.__new__(OctopoesAPIConnector)
    connector.client = "test"
    connector.session = Mock()
    connector.session.get.return_value.content = b'{"count":0,"items":[]}'

    result = connector.list_findings(
        {RiskLevelSeverity.HIGH}, datetime.now(UTC), group="web-security", tag="misconfiguration"
    )

    assert result.count == 0
    params = connector.session.get.call_args.kwargs["params"]
    assert params["group"] == "web-security"
    assert params["tag"] == "misconfiguration"

    connector.list_findings({RiskLevelSeverity.HIGH}, datetime.now(UTC))
    params = connector.session.get.call_args.kwargs["params"]
    assert "group" not in params
    assert "tag" not in params


def test_out_of_range_page_still_uses_actual_filtered_count():
    session = Mock()
    session.client.query.return_value = [[2]]
    repository = XTDBOOIRepository(Mock(), session)
    repository.query = Mock(return_value=[])

    result = repository.list_findings(
        {RiskLevelSeverity.HIGH}, datetime.now(UTC), offset=25, limit=5, group="web-security"
    )

    assert result.count == 2
    assert result.items == []
    assert '[?finding_type :KATFindingType/groups "web-security"]' in session.client.query.call_args.args[0]
