from reports.report_types.open_ports_report.report import OpenPortsReport


def test_open_ports_report_ip_no_port(mock_octopoes_api_connector, valid_time, service, hostname, ipaddressv4, ip_port):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort]": {ipaddressv4.reference: []},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPPort.<ip_port[is IPService].service": {ip_port.reference: []},
    }

    report = OpenPortsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data[str(ipaddressv4.address)] == {"ports": {}, "hostnames": [hostname.name], "services": {}}


def test_open_ports_report_ip_one_port(
    mock_octopoes_api_connector, valid_time, service, hostname, ipaddressv4, ip_port
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort]": {ipaddressv4.reference: [ip_port]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPPort.<ip_port[is IPService].service": {ip_port.reference: [service]},
    }

    report = OpenPortsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data[str(ipaddressv4.address)] == {
        "ports": {80: False},
        "hostnames": [hostname.name],
        "services": {80: [service.name]},
    }


def test_open_ports_report_ip_multiple_ports_sorting(
    mock_octopoes_api_connector, valid_time, service, hostname, ipaddressv4, ip_port, ip_port_443
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is IPPort]": {ipaddressv4.reference: [ip_port_443, ip_port]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPPort.<ip_port[is IPService].service": {ip_port_443.reference: [service], ip_port.reference: [service]},
    }

    report = OpenPortsReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert data[str(ipaddressv4.address)] == {
        "ports": {80: False, 443: False},
        "hostnames": [hostname.name],
        "services": {80: [service.name], 443: [service.name]},
    }


def test_open_ports_report_hostname_one_port(
    mock_octopoes_api_connector, valid_time, service, hostname, ipaddressv4, ip_port
):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: [ipaddressv4]},
        "IPAddress.<address[is IPPort]": {ipaddressv4.reference: [ip_port]},
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "IPPort.<ip_port[is IPService].service": {ip_port.reference: [service]},
    }

    report = OpenPortsReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert data[str(ipaddressv4.address)] == {
        "ports": {80: False},
        "hostnames": [hostname.name],
        "services": {80: [service.name]},
    }
