from reports.report_types.tls_report.report import TLSReport


def test_tls_report_no_suites_no_findings(mock_octopoes_api_connector, valid_time, ip_service, tree_data_no_findings):
    mock_octopoes_api_connector.queries = {"IPService.<ip_service[is TLSCipher]": {ip_service.reference: []}}

    report = TLSReport(mock_octopoes_api_connector)
    result = report.generate_data(str(ip_service.reference), valid_time)

    data = result[ip_service.primary_key]

    assert data["suites"] == {}
    assert data["findings"] == []
    assert data["suites_with_findings"] == []


def test_tls_report_multiple_findings_and_suites(
    cipher, mock_octopoes_api_connector, valid_time, ip_service, query_data_tls_findings_and_suites
):
    mock_octopoes_api_connector.queries = {
        "IPService.<ip_service[is TLSCipher]": {ip_service.reference: [cipher]},
        "TLSCipher.<ooi[is Finding]": {cipher.reference: query_data_tls_findings_and_suites},
    }

    report = TLSReport(mock_octopoes_api_connector)
    result = report.generate_data(str(ip_service.reference), valid_time)

    data = result[ip_service.primary_key]

    assert len(data["suites"]) == 1
    assert list(data["suites"].keys())[0] == "TLSv1"
    assert data["suites"]["TLSv1"][0]["cipher_suite_name"] == "ECDHE-RSA-AES128-SHA"
    assert data["suites"]["TLSv1"][1]["cipher_suite_name"] == "ECDHE-RSA-AES256-SHA"

    assert len(data["findings"]) == 3
    assert (
        data["findings"][0].primary_key
        == "Finding|TLSCipher|testnetwork|192.0.2.1|tcp|80|domain|KAT-RECOMMENDATION-BAD-CIPHER"
    )
    assert (
        data["findings"][1].primary_key == "Finding|TLSCipher|testnetwork|192.0.2.1|tcp|80|domain|KAT-MEDIUM-BAD-CIPHER"
    )
    assert (
        data["findings"][2].primary_key
        == "Finding|TLSCipher|testnetwork|192.0.2.1|tcp|80|domain|KAT-CRITICAL-BAD-CIPHER"
    )

    assert len(data["suites_with_findings"]) == 2
    assert data["suites_with_findings"][0] == "ECDHE-RSA-AES128-SHA"
    assert data["suites_with_findings"][1] == "ECDHE-RSA-AES256-SHA"
