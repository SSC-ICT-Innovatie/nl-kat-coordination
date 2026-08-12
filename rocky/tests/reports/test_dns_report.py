from reports.report_types.dns_report.report import DNSReport

from octopoes.models.tree import ReferenceTree


def test_dns_report_no_findings(mock_octopoes_api_connector, valid_time, hostname, tree_data_no_findings):
    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_no_findings)}

    report = DNSReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    assert data["records"] == []
    assert data["security"] == {"spf": True, "dkim": True, "dmarc": True, "dnssec": True, "caa": True}
    assert data["finding_types"] == []


def test_dns_report_two_findings_one_finding_type(
    mock_octopoes_api_connector,
    valid_time,
    hostname,
    finding_type_kat_invalid_spf,
    finding_type_kat_nameserver_no_ipv6,
    finding_type_kat_no_two_ipv6,
    tree_data_dns_findings,
):
    mock_octopoes_api_connector.oois = {
        finding_type_kat_invalid_spf.reference: finding_type_kat_invalid_spf,
        finding_type_kat_nameserver_no_ipv6.reference: finding_type_kat_nameserver_no_ipv6,
        finding_type_kat_no_two_ipv6.reference: finding_type_kat_no_two_ipv6,
    }

    mock_octopoes_api_connector.tree = {hostname.reference: ReferenceTree.model_validate(tree_data_dns_findings)}

    report = DNSReport(mock_octopoes_api_connector)
    data = report.generate_data(str(hostname.reference), valid_time)

    assert len(data["records"]) == 2
    assert data["records"][0]["type"] == "A"
    assert data["records"][0]["ttl"] == ""
    assert data["records"][1]["type"] == "SOA"
    assert data["records"][1]["ttl"] == 60

    assert data["security"] == {"spf": False, "dkim": False, "dmarc": False, "dnssec": False, "caa": False}

    assert len(data["finding_types"]) == 3
    assert data["finding_types"][0]["finding_type"] == finding_type_kat_nameserver_no_ipv6
    assert data["finding_types"][1]["finding_type"] == finding_type_kat_invalid_spf
    assert data["finding_types"][2]["finding_type"] == finding_type_kat_no_two_ipv6
