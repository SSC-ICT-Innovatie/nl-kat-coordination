from reports.report_types.systems_report.report import SystemReport, SystemType


def test_systems_report_no_systems(mock_octopoes_api_connector, valid_time, hostname):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {"Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: []}}

    report = SystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data["services"] == {}
    assert data["summary"]["total_systems"] == 0
    assert data["summary"]["total_domains"] == 0


def test_systems_simple_web_system(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4, service):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPAddress.<address[is IPPort].<ip_port [is IPService].service": {ipaddressv4.reference: [service]},
        "IPAddress.<address[is IPPort].<ooi [is SoftwareInstance].software": {ipaddressv4.reference: []},
        "IPAddress.<address[is IPPort].<ip_port [is IPService].<ip_service [is Website]": {ipaddressv4.reference: []},
    }

    report = SystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["services"]) == 1
    assert len(data["services"][ipaddressv4.reference]["services"]) == 1
    assert data["services"][ipaddressv4.reference]["hostnames"] == [hostname.reference]
    assert data["services"][ipaddressv4.reference]["services"] == [SystemType.DNS]
    assert data["summary"]["total_systems"] == 1
    assert data["summary"]["total_domains"] == 1


def test_systems_complex_system(mock_octopoes_api_connector, valid_time, hostname, ipaddressv4, service, software):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPAddress.<address[is IPPort].<ip_port [is IPService].service": {ipaddressv4.reference: [service]},
        "IPAddress.<address[is IPPort].<ooi [is SoftwareInstance].software": {ipaddressv4.reference: [software]},
        "IPAddress.<address[is IPPort].<ip_port [is IPService].<ip_service [is Website]": {ipaddressv4.reference: []},
    }

    report = SystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["services"]) == 1
    assert len(data["services"][ipaddressv4.reference]["services"]) == 2
    assert data["services"][ipaddressv4.reference]["hostnames"] == [hostname.reference]
    assert data["services"][ipaddressv4.reference]["services"] == [SystemType.DNS, SystemType.DICOM]
    assert data["summary"]["total_systems"] == 1
    assert data["summary"]["total_domains"] == 1


def test_systems_two_systems(
    mock_octopoes_api_connector, valid_time, service, hostname, ipaddressv4, ipaddressv6, software
):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}

    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4, ipaddressv6]},
        "IPAddress.<address[is ResolvedHostname].hostname": {
            ipaddressv4.reference: [hostname],
            ipaddressv6.reference: [hostname],
        },
        "IPAddress.<address[is IPPort].<ip_port [is IPService].service": {
            ipaddressv4.reference: [service],
            ipaddressv6.reference: [],
        },
        "IPAddress.<address[is IPPort].<ooi [is SoftwareInstance].software": {
            ipaddressv4.reference: [],
            ipaddressv6.reference: [software],
        },
        "IPAddress.<address[is IPPort].<ip_port [is IPService].<ip_service [is Website]": {
            ipaddressv4.reference: [],
            ipaddressv6.reference: [],
        },
    }

    report = SystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["services"]) == 2
    assert len(data["services"][ipaddressv4.reference]["services"]) == 1
    assert len(data["services"][ipaddressv6.reference]["services"]) == 1
    assert data["services"][ipaddressv4.reference]["services"] == [SystemType.DNS]
    assert data["services"][ipaddressv6.reference]["services"] == [SystemType.DICOM]
    assert data["summary"]["total_systems"] == 2
    assert data["summary"]["total_domains"] == 1
