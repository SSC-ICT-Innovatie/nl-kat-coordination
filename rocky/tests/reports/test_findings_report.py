from reports.report_types.findings_report.report import FindingsReport

from octopoes.models.tree import ReferenceTree


def test_findings_report_no_findings(mock_octopoes_api_connector, valid_time, hostname, tree_data_no_findings):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_no_findings)}

    report = FindingsReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    assert data["summary"]["total_by_severity"]["critical"] == 0
    assert data["summary"]["total_by_severity_per_finding_type"]["critical"] == 0
    assert data["summary"]["total_finding_types"] == 0
    assert data["summary"]["total_occurrences"] == 0


def test_findings_report_two_findings_one_finding_type(
    mock_octopoes_api_connector, valid_time, hostname, tree_data_findings, finding_types
):
    mock_octopoes_api_connector.oois = {
        finding_types[0].reference: finding_types[0],
        finding_types[1].reference: finding_types[1],
    }

    # This tree data contains four OOIs, three of which are findings that contain two different finding_types.
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_findings)}

    report = FindingsReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    assert data["finding_types"][0]["finding_type"] == finding_types[0]
    assert data["finding_types"][1]["finding_type"] == finding_types[1]
    assert data["summary"]["total_by_severity"]["critical"] == 3
    assert data["summary"]["total_by_severity_per_finding_type"]["critical"] == 2
    assert data["summary"]["total_finding_types"] == 2
    assert data["summary"]["total_occurrences"] == 3
