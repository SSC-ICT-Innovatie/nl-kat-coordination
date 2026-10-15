from reports.report_types.findings_report.report import FindingsReport
from tools.ooi_helpers import SOFTWARE_FINDINGS_PATH

from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding, RiskLevelSeverity
from octopoes.models.ooi.software import Software, SoftwareInstance
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


def test_findings_report_includes_cve_bound_to_software(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4):
    """A CVE hangs on the Software OOI, so the object tree never reaches it (#5321).

    The report has to walk the last two hops -- SoftwareInstance -> Software -> Finding -- itself,
    and report the finding on the asset running that software rather than on the Software OOI.
    """
    software = Software(name="nginx", version="1.0")
    instance = SoftwareInstance(ooi=ipaddressv4.reference, software=software.reference)
    finding_type = CVEFindingType(id="CVE-2024-0001", risk_score=9.8, risk_severity=RiskLevelSeverity.CRITICAL)
    finding = Finding(finding_type=finding_type.reference, ooi=software.reference, description="")

    mock_octopoes_api_connector.oois = {finding_type.reference: finding_type}
    mock_octopoes_api_connector.tree = {
        hostname.reference: ReferenceTree.model_validate(
            {
                "root": {"reference": str(hostname.reference), "children": {}},
                "store": {str(instance.reference): instance.model_dump(mode="json")},
            }
        )
    }
    mock_octopoes_api_connector.queries = {SOFTWARE_FINDINGS_PATH: {str(instance.reference): [finding]}}

    report = FindingsReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    assert data["finding_types"][0]["finding_type"] == finding_type
    assert data["summary"]["total_occurrences"] == 1
    assert data["summary"]["total_by_severity"]["critical"] == 1

    # Reported on the asset running the software, not on the shared Software OOI the CVE hangs on.
    occurrence = data["finding_types"][0]["occurrences"][0]
    assert occurrence["affected_ooi"] == ipaddressv4.reference
    assert occurrence["finding"].ooi == software.reference


def test_findings_report_attributes_direct_findings_to_their_own_ooi(
    mock_octopoes_api_connector, valid_time, hostname, tree_data_findings, finding_types
):
    """Findings that hang on the object itself keep pointing at it."""
    mock_octopoes_api_connector.oois = {finding_types[0].reference: finding_types[0]}
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_findings)}

    report = FindingsReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    for finding_type in data["finding_types"]:
        for occurrence in finding_type["occurrences"]:
            assert occurrence["affected_ooi"] == occurrence["finding"].ooi


def test_findings_report_reports_shared_software_once(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4):
    """One package reached through two instances is one occurrence, on the first asset found."""
    software = Software(name="nginx", version="1.0")
    instances = [
        SoftwareInstance(ooi=Reference.from_str(f"IPPort|testnetwork|1.1.1.1|tcp|{port}"), software=software.reference)
        for port in (80, 443)
    ]
    finding_type = CVEFindingType(id="CVE-2024-0001", risk_score=9.8, risk_severity=RiskLevelSeverity.CRITICAL)
    finding = Finding(finding_type=finding_type.reference, ooi=software.reference, description="")

    mock_octopoes_api_connector.oois = {finding_type.reference: finding_type}
    mock_octopoes_api_connector.tree = {
        hostname.reference: ReferenceTree.model_validate(
            {
                "root": {"reference": str(hostname.reference), "children": {}},
                "store": {str(i.reference): i.model_dump(mode="json") for i in instances},
            }
        )
    }
    mock_octopoes_api_connector.queries = {
        SOFTWARE_FINDINGS_PATH: {str(instance.reference): [finding] for instance in instances}
    }

    report = FindingsReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    occurrences = data["finding_types"][0]["occurrences"]
    assert len(occurrences) == 1
    assert occurrences[0]["affected_ooi"] == instances[0].ooi
