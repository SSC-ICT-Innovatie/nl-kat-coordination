from reports.report_types.ipv6_report.report import IPv6Report


def test_ipv6_report_hostname_with_ipv6(mock_octopoes_api_connector, valid_time, hostname, ipaddressv6, ipaddressv4):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4, ipaddressv6]}
    }

    report = IPv6Report(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data[hostname.name] == {"enabled": True}


def test_ipv6_report_hostname_without_ipv6(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]}
    }

    report = IPv6Report(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data[hostname.name] == {"enabled": False}


def test_ipv6_report_ipv4_without_ipv6(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
    }

    report = IPv6Report(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data[hostname.name] == {"enabled": False}


def test_ipv6_report_ipv4_with_ipv6(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4, ipaddressv6):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4, ipaddressv6]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
    }

    report = IPv6Report(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data[hostname.name] == {"enabled": True}


def test_ipv6_report_ipv6_wit_ipv6(mock_octopoes_api_connector, valid_time, hostname, ipaddressv6):
    mock_octopoes_api_connector.oois = {ipaddressv6.reference: ipaddressv6}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv6]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv6.reference: [hostname]},
    }

    report = IPv6Report(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv6.reference], valid_time)[ipaddressv6.reference]

    assert data[hostname.name] == {"enabled": True}
