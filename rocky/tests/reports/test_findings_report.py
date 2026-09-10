from reports.report_types.findings_report.report import FindingsReport

from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding
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


def test_findings_report_dedups_software_findings(
    mock_octopoes_api_connector, valid_time, hostname, tree_data_no_findings, finding_types
):
    """Findings bound to Software arrive via the Software query path, not get_tree
    (Software._traversable is False). SoftwareInstance.software is many-to-one,
    so multiple instances reaching the same Software yield the same Finding — the
    report must dedup by reference, not count it once per instance."""
    software_finding = Finding(
        finding_type=finding_types[0].reference,
        ooi=Reference.from_str("Software|WordPress|6.5.2|"),
        description="Non-CVE bug",
    )
    mock_octopoes_api_connector.oois = {finding_types[0].reference: finding_types[0]}
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_no_findings)}
    mock_octopoes_api_connector.queries = {
        "Hostname.<netloc [is HostnameHTTPURL].<ooi [is SoftwareInstance].software.<ooi [is Finding]": {
            hostname.reference: [software_finding, software_finding]  # http + https instances
        }
    }

    data = FindingsReport(mock_octopoes_api_connector).generate_data(str(hostname.reference), valid_time)

    assert data["summary"]["total_finding_types"] == 1
    assert data["summary"]["total_occurrences"] == 1  # deduplicated, not 2
