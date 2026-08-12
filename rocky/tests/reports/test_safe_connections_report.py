from reports.report_types.safe_connections_report.report import SafeConnectionsReport


def test_safe_connections_report_no_finding_types(mock_octopoes_api_connector, valid_time, hostname):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {"Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: []}}

    report = SafeConnectionsReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data["sc_ips"] == {}
    assert data["number_of_available"] == 0
    assert data["number_of_ips"] == 0


def test_safe_connections_report_single_cipher_finding_type(
    mock_octopoes_api_connector, valid_time, ipaddressv4, cipher_finding_type, finding_types
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort].<ip_port [is IPService]"
        ".<ip_service [is TLSCipher].<ooi[is Finding].finding_type": {
            ipaddressv4.reference: [cipher_finding_type, finding_types[0]]
        }
    }

    report = SafeConnectionsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data["sc_ips"][ipaddressv4.reference] == [cipher_finding_type]
    assert data["number_of_available"] == 0
    assert data["number_of_ips"] == 1


def test_safe_connections_report_multiple_cipher_finding_types(
    mock_octopoes_api_connector, valid_time, ipaddressv4, cipher_finding_types, finding_types
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort].<ip_port [is IPService]"
        ".<ip_service [is TLSCipher].<ooi[is Finding].finding_type": {
            ipaddressv4.reference: cipher_finding_types + finding_types
        }
    }

    report = SafeConnectionsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data["sc_ips"][ipaddressv4.reference] == cipher_finding_types
    assert data["number_of_available"] == 0
    assert data["number_of_ips"] == 1


def test_safe_connections_report_no_cipher_finding_types(
    mock_octopoes_api_connector, valid_time, ipaddressv4, finding_types
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort].<ip_port [is IPService]"
        ".<ip_service [is TLSCipher].<ooi[is Finding].finding_type": {ipaddressv4.reference: finding_types}
    }

    report = SafeConnectionsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data["sc_ips"][ipaddressv4.reference] == []
    assert data["number_of_available"] == 1
    assert data["number_of_ips"] == 1
