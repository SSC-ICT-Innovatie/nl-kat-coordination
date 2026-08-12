from reports.report_types.rpki_report.report import RPKIReport


def test_rpki_report_no_ip(mock_octopoes_api_connector, valid_time, hostname):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {"Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: []}}

    report = RPKIReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data["rpki_ips"] == {}
    assert data["number_of_available"] == 0
    assert data["number_of_compliant"] == 0
    assert data["number_of_valid"] == 0
    assert data["number_of_ips"] == 0


def test_rpki_ip_valid(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4, service):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}

    mock_octopoes_api_connector.queries = {"IPAddress.<ooi[is Finding].finding_type": {ipaddressv4.reference: []}}

    report = RPKIReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data["number_of_available"] == 1
    assert data["number_of_compliant"] == 1
    assert data["number_of_valid"] == 1
    assert data["number_of_ips"] == 1

    assert data["rpki_ips"][ipaddressv4.reference] == {"exists": True, "valid": True}


def test_rpki_hostname_with_ip_valid(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4, service):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]},
        "IPAddress.<ooi[is Finding].finding_type": {ipaddressv4.reference: []},
    }

    report = RPKIReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data["number_of_available"] == 1
    assert data["number_of_compliant"] == 1
    assert data["number_of_valid"] == 1
    assert data["number_of_ips"] == 1

    assert data["rpki_ips"][ipaddressv4.reference] == {"exists": True, "valid": True}


def test_rpki_hostname_with_two_ips_invalid(
    mock_octopoes_api_connector,
    valid_time,
    hostname,
    ipaddressv4,
    ipaddressv6,
    service,
    no_rpki_finding_type,
    invalid_rpki_finding_type,
):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4, ipaddressv6]},
        "IPAddress.<ooi[is Finding].finding_type": {
            ipaddressv4.reference: [no_rpki_finding_type, invalid_rpki_finding_type],
            ipaddressv6.reference: [invalid_rpki_finding_type],
        },
    }

    report = RPKIReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data["rpki_ips"][ipaddressv4.reference] == {"exists": False, "valid": False}
    assert data["rpki_ips"][ipaddressv6.reference] == {"exists": True, "valid": False}
    assert data["number_of_available"] == 1
    assert data["number_of_compliant"] == 0
    assert data["number_of_valid"] == 0
    assert data["number_of_ips"] == 2
