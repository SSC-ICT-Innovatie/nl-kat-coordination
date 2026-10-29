from reports.report_types.findings_report.report import FindingsReport

from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.software import SoftwareInstance
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


def test_findings_report_dedups_software_findings_same_install(
    mock_octopoes_api_connector, valid_time, hostname, tree_data_no_findings, finding_types
):
    """Findings bound to Software arrive via the Software query path, not
    get_tree (Software._traversable is False). Two SoftwareInstances on the
    same port but different paths (/, /blog/) are the same install — the
    report must dedup by install, not count the finding twice."""
    software_ref = Reference.from_str("Software|WordPress|6.5.2|")
    software_finding = Finding(finding_type=finding_types[0].reference, ooi=software_ref, description="Non-CVE bug")
    instances = [
        SoftwareInstance(ooi=Reference.from_str("HostnameHTTPURL|https|internet|host|443|/"), software=software_ref),
        SoftwareInstance(
            ooi=Reference.from_str("HostnameHTTPURL|https|internet|host|443|/blog/"), software=software_ref
        ),
    ]
    mock_octopoes_api_connector.oois = {finding_types[0].reference: finding_types[0]}
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_no_findings)}
    mock_octopoes_api_connector.queries = {
        "Hostname.<netloc [is HostnameHTTPURL].<ooi [is SoftwareInstance]": {hostname.reference: instances},
        "Software.<ooi [is Finding]": {str(software_ref): [software_finding]},
    }

    data = FindingsReport(mock_octopoes_api_connector).generate_data(str(hostname.reference), valid_time)

    assert data["summary"]["total_finding_types"] == 1
    assert data["summary"]["total_occurrences"] == 1  # same install, different paths → 1


def test_findings_report_counts_software_findings_per_install(
    mock_octopoes_api_connector, valid_time, hostname, tree_data_no_findings, finding_types
):
    """Two SoftwareInstances on different ports (:443, :8443) are distinct
    installs — even though they share the same Software and thus the same
    Finding OOI, the report must count one per install."""
    software_ref = Reference.from_str("Software|WordPress|6.5.2|")
    software_finding = Finding(finding_type=finding_types[0].reference, ooi=software_ref, description="Non-CVE bug")
    instances = [
        SoftwareInstance(ooi=Reference.from_str("HostnameHTTPURL|https|internet|host|443|/"), software=software_ref),
        SoftwareInstance(ooi=Reference.from_str("HostnameHTTPURL|https|internet|host|8443|/"), software=software_ref),
    ]
    mock_octopoes_api_connector.oois = {finding_types[0].reference: finding_types[0]}
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_no_findings)}
    mock_octopoes_api_connector.queries = {
        "Hostname.<netloc [is HostnameHTTPURL].<ooi [is SoftwareInstance]": {hostname.reference: instances},
        "Software.<ooi [is Finding]": {str(software_ref): [software_finding]},
    }

    data = FindingsReport(mock_octopoes_api_connector).generate_data(str(hostname.reference), valid_time)

    assert data["summary"]["total_finding_types"] == 1
    assert data["summary"]["total_occurrences"] == 2  # distinct installs → 2
