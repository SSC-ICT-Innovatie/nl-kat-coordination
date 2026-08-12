from reports.report_types.name_server_report.report import NameServerSystemReport


def test_name_server_report_no_hostname(mock_octopoes_api_connector, valid_time, ipaddressv4):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}

    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: []}
    }

    report = NameServerSystemReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert len(data["name_server_checks"].checks) == 0
    assert data["name_server_checks"].has_dnssec == 0
    assert data["name_server_checks"].has_valid_dnssec == 0
    assert data["name_server_checks"].no_uncommon_ports == 0
    assert data["finding_types"] == []


def test_name_server_report_no_finding_types(mock_octopoes_api_connector, valid_time, hostname):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type": {
            hostname.reference: []
        },
        "Hostname.<ooi[is Finding].finding_type": {hostname.reference: []},
    }

    report = NameServerSystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["name_server_checks"].checks) == 1
    assert data["name_server_checks"].has_dnssec == 1
    assert data["name_server_checks"].has_valid_dnssec == 1
    assert data["name_server_checks"].no_uncommon_ports == 1
    assert data["finding_types"] == []

    assert data["name_server_checks"].checks[0].has_dnssec is True
    assert data["name_server_checks"].checks[0].has_valid_dnssec is True
    assert data["name_server_checks"].checks[0].no_uncommon_ports is True


def test_name_server_report_multiple_finding_types(
    mock_octopoes_api_connector,
    valid_time,
    hostname,
    ipaddressv4,
    finding_type_kat_uncommon_open_port,
    finding_type_kat_open_sysadmin_port,
    finding_type_kat_open_database_port,
    finding_type_kat_no_dnssec,
    finding_type_kat_invalid_dnssec,
    finding_types,
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}

    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type": {
            hostname.reference: [
                finding_type_kat_uncommon_open_port,
                finding_type_kat_open_sysadmin_port,
                finding_type_kat_open_database_port,
            ]
            + finding_types
        },
        "Hostname.<ooi[is Finding].finding_type": {
            hostname.reference: [finding_type_kat_no_dnssec, finding_type_kat_invalid_dnssec] + finding_types
        },
    }

    report = NameServerSystemReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert len(data["name_server_checks"].checks) == 1
    assert data["name_server_checks"].has_dnssec == 0
    assert data["name_server_checks"].has_valid_dnssec == 0
    assert data["name_server_checks"].no_uncommon_ports == 0

    assert data["name_server_checks"].checks[0].has_dnssec is False
    assert data["name_server_checks"].checks[0].has_valid_dnssec is False
    assert data["name_server_checks"].checks[0].no_uncommon_ports is False
    assert data["finding_types"] == [
        finding_type_kat_uncommon_open_port,
        finding_type_kat_open_sysadmin_port,
        finding_type_kat_open_database_port,
    ]
