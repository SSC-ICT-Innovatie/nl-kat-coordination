from reports.report_types.mail_report.report import MailReport


def test_mail_report_no_findings(mock_octopoes_api_connector, valid_time, hostname):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {"Hostname.<ooi[is Finding].finding_type": {hostname.reference: []}}

    report = MailReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["finding_types"]) == 0
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 1
    assert data["number_of_dkim"] == 1
    assert data["number_of_dmarc"] == 1


def test_mail_report_spf_finding(mock_octopoes_api_connector, valid_time, hostname, finding_type_kat_no_spf):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<ooi[is Finding].finding_type": {hostname.reference: [finding_type_kat_no_spf]}
    }

    report = MailReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["finding_types"]) == 1
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 0
    assert data["number_of_dkim"] == 1
    assert data["number_of_dmarc"] == 1


def test_mail_report_dkim_finding(
    mock_octopoes_api_connector, valid_time, ipaddressv4, hostname, finding_type_kat_no_dkim
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "Hostname.<ooi[is Finding].finding_type": {hostname.reference: [finding_type_kat_no_dkim]},
    }

    report = MailReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert len(data["finding_types"]) == 1
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 1
    assert data["number_of_dkim"] == 0
    assert data["number_of_dmarc"] == 1


def test_mail_report_dmarc_finding(
    mock_octopoes_api_connector, valid_time, ipaddressv4, hostname, finding_type_kat_no_dmarc
):
    mock_octopoes_api_connector.oois = {ipaddressv4.reference: ipaddressv4}
    mock_octopoes_api_connector.queries = {
        "IPAddress.<address[is ResolvedHostname].hostname": {ipaddressv4.reference: [hostname]},
        "Hostname.<ooi[is Finding].finding_type": {hostname.reference: [finding_type_kat_no_dmarc]},
    }

    report = MailReport(mock_octopoes_api_connector)

    data = report.collect_data([ipaddressv4.reference], valid_time)[ipaddressv4.reference]

    assert len(data["finding_types"]) == 1
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 1
    assert data["number_of_dkim"] == 1
    assert data["number_of_dmarc"] == 0


def test_mail_report_multiple_findings(
    mock_octopoes_api_connector,
    valid_time,
    hostname,
    finding_type_kat_no_spf,
    finding_type_kat_no_dkim,
    finding_type_kat_no_dmarc,
):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<ooi[is Finding].finding_type": {
            hostname.reference: [finding_type_kat_no_spf, finding_type_kat_no_dkim, finding_type_kat_no_dmarc]
        }
    }

    report = MailReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert len(data["finding_types"]) == 3
    assert data["number_of_hostnames"] == 1
    assert data["number_of_spf"] == 0
    assert data["number_of_dkim"] == 0
    assert data["number_of_dmarc"] == 0
