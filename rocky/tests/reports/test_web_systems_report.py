from reports.report_types.web_system_report.report import WebSystemReport


def test_web_report_no_findings(mock_octopoes_api_connector, valid_time, hostname, security_txt):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: []},
        "Hostname.<hostname[is Website].<website[is HTTPResource].<ooi[is Finding].finding_type": {
            hostname.reference: []
        },
        "Hostname.<hostname[is Website].<website[is HTTPResource].<resource[is HTTPHeader]."
        "<ooi[is Finding].finding_type": {hostname.reference: []},
        "Hostname.<netloc[is HostnameHTTPURL].<ooi[is Finding].finding_type": {hostname.reference: []},
        "Hostname.<hostname[is Website].<ooi[is Finding].finding_type": {hostname.reference: []},
        "Hostname.<hostname[is Website].<website[is SecurityTXT]": {hostname.reference: [security_txt]},
        "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type": {
            hostname.reference: []
        },
        "Hostname.<hostname[is Website].certificate.<ooi[is Finding].finding_type": {hostname.reference: []},
    }

    report = WebSystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    assert bool(data["web_checks"])


def test_web_report_all_findings(
    mock_octopoes_api_connector, valid_time, hostname, security_txt, web_report_finding_types
):
    mock_octopoes_api_connector.oois = {hostname.reference: hostname}
    mock_octopoes_api_connector.queries = {
        "Hostname.<hostname[is ResolvedHostname].address": {hostname.reference: []},
        "Hostname.<hostname[is Website].<website[is HTTPResource].<ooi[is Finding].finding_type": {
            hostname.reference: web_report_finding_types
        },
        "Hostname.<hostname[is Website].<website[is HTTPResource].<resource[is HTTPHeader]."
        "<ooi[is Finding].finding_type": {hostname.reference: web_report_finding_types},
        "Hostname.<netloc[is HostnameHTTPURL].<ooi[is Finding].finding_type": {
            hostname.reference: web_report_finding_types
        },
        "Hostname.<hostname[is Website].<ooi[is Finding].finding_type": {hostname.reference: web_report_finding_types},
        "Hostname.<hostname[is Website].<website[is SecurityTXT]": {hostname.reference: []},
        "Hostname.<hostname[is ResolvedHostname].address.<address[is IPPort].<ooi[is Finding].finding_type": {
            hostname.reference: web_report_finding_types
        },
        "Hostname.<hostname[is Website].certificate.<ooi[is Finding].finding_type": {
            hostname.reference: web_report_finding_types
        },
    }

    report = WebSystemReport(mock_octopoes_api_connector)

    data = report.collect_data([hostname.reference], valid_time)[hostname.reference]

    checks = data["web_checks"]

    assert checks.has_csp == 0
    assert checks.has_no_csp_vulnerabilities == 0
    assert checks.redirects_http_https == 0
    assert checks.offers_https == 0
    assert checks.has_security_txt == 0
    assert checks.no_uncommon_ports == 0
    assert checks.has_certificates == 0
    assert checks.certificates_not_expired == 0
    assert checks.certificates_not_expiring_soon == 0
