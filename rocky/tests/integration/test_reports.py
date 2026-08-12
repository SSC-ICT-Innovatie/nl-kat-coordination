from dataclasses import asdict

from reports.report_types.aggregate_organisation_report.report import AggregateOrganisationReport
from reports.report_types.definitions import MultiReport, Report
from reports.report_types.multi_organization_report.report import MultiOrganizationReport, collect_report_data
from reports.report_types.systems_report.report import SystemReport, SystemType
from reports.report_types.web_system_report.report import WebSystemReport
from reports.runner.report_runner import aggregate_reports

from octopoes.api.models import Declaration
from octopoes.connector.octopoes import OctopoesAPIConnector
from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding, KATFindingType, RiskLevelSeverity
from octopoes.models.ooi.reports import ReportData
from tests.integration.conftest import seed_system


def test_web_report(octopoes_api_connector: OctopoesAPIConnector, valid_time):
    seed_system(octopoes_api_connector, valid_time)

    report = WebSystemReport(octopoes_api_connector)
    input_ooi = Reference.from_str("Hostname|test|example.com")
    data = report.collect_data([input_ooi], valid_time)[input_ooi]

    assert data["input_ooi"] == input_ooi
    assert len(data["finding_types"]) == 1
    assert len(data["web_checks"]) == 1

    assert asdict(data["web_checks"].checks[0]) == {
        "has_csp": True,
        "has_no_csp_vulnerabilities": True,
        "redirects_http_https": True,
        "offers_https": True,
        "has_security_txt": True,
        "no_uncommon_ports": True,
        "has_certificates": True,
        "certificates_not_expired": True,
        "certificates_not_expiring_soon": True,
    }

    finding = Finding(
        finding_type=Reference.from_str("KATFindingType|KAT-NO-CSP"),
        ooi=Reference.from_str("HTTPResource|test|192.0.2.3|tcp|25|smtp|test|example.com|http|test|example.com|80|/"),
    )
    octopoes_api_connector.save_declaration(Declaration(ooi=finding, valid_time=valid_time))
    checks = report.collect_data([input_ooi], valid_time)[input_ooi]["web_checks"].checks
    assert checks[0].has_csp is False
    assert checks[0].has_no_csp_vulnerabilities is False

    finding = Finding(
        finding_type=Reference.from_str("KATFindingType|KAT-NO-CERTIFICATE"),
        ooi=Reference.from_str("Website|test|192.0.2.3|tcp|25|smtp|test|example.com"),
    )
    octopoes_api_connector.save_declaration(Declaration(ooi=finding, valid_time=valid_time))
    data = report.collect_data([input_ooi], valid_time)[input_ooi]
    assert data["web_checks"].checks[0].offers_https is False

    assert len(data["finding_types"]) == 3


def test_system_report(octopoes_api_connector: OctopoesAPIConnector, valid_time):
    seed_system(octopoes_api_connector, valid_time)

    report = SystemReport(octopoes_api_connector)
    input_ooi = Reference.from_str("Hostname|test|example.com")
    data = report.collect_data([input_ooi], valid_time)[input_ooi]

    assert data["input_ooi"] == input_ooi
    assert data["summary"] == {"total_domains": 7, "total_systems": 2}
    assert data["services"] == {
        "IPAddressV4|test|192.0.2.3": {
            "hostnames": [
                "Hostname|test|a.example.com",
                "Hostname|test|b.example.com",
                "Hostname|test|c.example.com",
                "Hostname|test|d.example.com",
                "Hostname|test|e.example.com",
                "Hostname|test|example.com",
            ],
            "services": [SystemType.DICOM, SystemType.MAIL, SystemType.OTHER, SystemType.WEB],
        },
        "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230": {
            "hostnames": [
                "Hostname|test|c.example.com",
                "Hostname|test|d.example.com",
                "Hostname|test|example.com",
                "Hostname|test|f.example.com",
            ],
            "services": [SystemType.WEB],
        },
    }


def test_aggregate_report(octopoes_api_connector: OctopoesAPIConnector, valid_time, hostname_oois, organization):
    seed_system(octopoes_api_connector, valid_time)

    reports: list[type[Report] | type[MultiReport]] = (
        AggregateOrganisationReport.reports["required"] + AggregateOrganisationReport.reports["optional"]
    )
    report_ids = [report_type.id for report_type in reports]
    _, data, _, _ = aggregate_reports(octopoes_api_connector, hostname_oois, report_ids, valid_time, organization.code)

    v4_test_hostnames = [
        "Hostname|test|a.example.com",
        "Hostname|test|b.example.com",
        "Hostname|test|c.example.com",
        "Hostname|test|d.example.com",
        "Hostname|test|e.example.com",
        "Hostname|test|example.com",
    ]

    assert data["systems"]["services"] == {
        "IPAddressV4|test|192.0.2.3": {
            "hostnames": v4_test_hostnames,
            "services": [SystemType.DICOM, SystemType.MAIL, SystemType.OTHER, SystemType.WEB],
        },
        "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230": {
            "hostnames": [
                "Hostname|test|c.example.com",
                "Hostname|test|d.example.com",
                "Hostname|test|example.com",
                "Hostname|test|f.example.com",
            ],
            "services": [SystemType.WEB],
        },
    }

    assert len(data["services"]["Dicom"]["IPAddressV4|test|192.0.2.3"]["hostnames"]) == 6
    assert len(data["services"]["Mail"]["IPAddressV4|test|192.0.2.3"]["hostnames"]) == 6
    assert len(data["services"]["Web"]["IPAddressV4|test|192.0.2.3"]["hostnames"]) == 6
    assert len(data["services"]["Other"]["IPAddressV4|test|192.0.2.3"]["hostnames"]) == 6

    assert "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230" not in data["services"]["Dicom"]
    assert "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230" not in data["services"]["Mail"]
    assert "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230" not in data["services"]["Other"]
    assert len(data["services"]["Web"]["IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"]["hostnames"]) == 4

    assert data["open_ports"] == {
        "192.0.2.3": {
            "ports": {22: False, 25: False, 443: False},
            "services": {22: ["ssh"], 25: ["smtp"], 443: ["https"]},
            "hostnames": [x.replace("Hostname|test|", "") for x in v4_test_hostnames],
        },
        "3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230": {
            "ports": {80: False},
            "services": {80: ["http"]},
            "hostnames": ["c.example.com", "d.example.com", "example.com", "f.example.com"],
        },
    }
    assert data["ipv6"] == {"example.com": {"enabled": True, "systems": ["Dicom", "Mail", "Other", "Web"]}}
    assert data["vulnerabilities"]["IPAddressV4|test|192.0.2.3"]["summary"] == {
        "total_findings": 6,
        "total_criticals": 0,
        "terms": ["CVE-2018-20677", "CVE-2019-8331", "RetireJS-jquerymigrate-f3a3"],
        "recommendations": [],
    }

    v4_vulnerabilities = data["vulnerabilities"]["IPAddressV4|test|192.0.2.3"]
    assert v4_vulnerabilities["title"] == "192.0.2.3"
    assert v4_vulnerabilities["vulnerabilities"]["CVE-2018-20677"]["occurrences"] == 2
    assert v4_vulnerabilities["vulnerabilities"]["RetireJS-jquerymigrate-f3a3"]["occurrences"] == 2
    assert v4_vulnerabilities["vulnerabilities"]["CVE-2019-8331"]["occurrences"] == 2

    v6_vulnerabilities = data["vulnerabilities"]["IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"]
    assert v6_vulnerabilities["title"] == "3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"
    assert v6_vulnerabilities["summary"] == {
        "total_findings": 6,
        "total_criticals": 0,
        "terms": ["CVE-2018-20677", "CVE-2019-8331", "RetireJS-jquerymigrate-f3a3"],
        "recommendations": [],
    }
    assert v6_vulnerabilities["title"] == "3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230"
    assert v6_vulnerabilities["vulnerabilities"]["CVE-2018-20677"]["occurrences"] == 2
    assert v6_vulnerabilities["vulnerabilities"]["RetireJS-jquerymigrate-f3a3"]["occurrences"] == 2
    assert v6_vulnerabilities["vulnerabilities"]["CVE-2019-8331"]["occurrences"] == 2

    assert data["basic_security"]["summary"]["Dicom"] == {
        "rpki": {"number_of_compliant": 1, "total": 1},
        "system_specific": {"number_of_compliant": 0, "total": 0, "checks": {}, "ips": {}},
        "safe_connections": {"number_of_compliant": 1, "total": 1},
    }
    assert data["basic_security"]["summary"]["Mail"] == {
        "rpki": {"number_of_compliant": 1, "total": 1},
        "system_specific": {
            "number_of_compliant": 1,
            "total": 1,
            "checks": {"SPF": 1, "DKIM": 1, "DMARC": 1},
            "ips": {"IPAddressV4|test|192.0.2.3": []},
        },
        "safe_connections": {"number_of_compliant": 1, "total": 1},
    }
    security_txt_finding_type = KATFindingType(
        id="KAT-NO-SECURITY-TXT",
        description="This hostname does not have a Security.txt file.",
        recommendation="Make sure there is a security.txt available.",
        risk_severity=RiskLevelSeverity.RECOMMENDATION,
    )
    assert data["basic_security"]["summary"]["Web"] == {
        "rpki": {"number_of_compliant": 2, "total": 2},
        "system_specific": {
            "number_of_compliant": 2,
            "total": 2,
            "checks": {
                "CSP Present": 2,
                "Secure CSP Header": 2,
                "Redirects HTTP to HTTPS": 2,
                "Offers HTTPS": 2,
                "Has a Security.txt": 2,
                "No unnecessary ports open": 2,
                "Has a certificate": 2,
                "Certificate is not expired": 2,
                "Certificate is not expiring soon": 2,
            },
            "ips": {
                "IPAddressV4|test|192.0.2.3": [security_txt_finding_type],
                "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230": [security_txt_finding_type],
            },
        },
        "safe_connections": {"number_of_compliant": 2, "total": 2},
    }
    assert data["basic_security"]["summary"]["Other"] == {
        "rpki": {"number_of_compliant": 1, "total": 1},
        "system_specific": {"number_of_compliant": 0, "total": 0, "checks": {}, "ips": {}},
        "safe_connections": {"number_of_compliant": 1, "total": 1},
    }

    assert data["total_findings"] == 3
    assert data["total_systems"] == 2


def test_multi_report(
    octopoes_api_connector: OctopoesAPIConnector,
    octopoes_api_connector_2: OctopoesAPIConnector,
    valid_time,
    hostname_oois,
    organization,
):
    seed_system(octopoes_api_connector, valid_time)
    seed_system(octopoes_api_connector_2, valid_time)

    reports = AggregateOrganisationReport.reports["required"] + AggregateOrganisationReport.reports["optional"]
    report_ids = [report_type.id for report_type in reports]
    _, data, _, _ = aggregate_reports(octopoes_api_connector, hostname_oois, report_ids, valid_time, organization.code)
    _, data_2, _, _ = aggregate_reports(
        octopoes_api_connector_2, hostname_oois, report_ids, valid_time, organization.code
    )

    report_data_object = ReportData(
        organization_code=octopoes_api_connector.client,
        organization_name="Test name",
        organization_tags=["test1"],
        data=data,
    )
    report_data_object_2 = ReportData(
        organization_code=octopoes_api_connector_2.client,
        organization_name="Name2",
        organization_tags=["test1", "test2", "test3"],
        data=data_2,
    )

    # Save second organization info in the first organization
    octopoes_api_connector.save_declaration(Declaration(ooi=report_data_object, valid_time=valid_time))
    octopoes_api_connector.save_declaration(Declaration(ooi=report_data_object_2, valid_time=valid_time))

    multi_report = MultiOrganizationReport(octopoes_api_connector)
    multi_report_data = collect_report_data(
        octopoes_api_connector, [str(report_data_object.reference), str(report_data_object_2.reference)], valid_time
    )
    multi_data = multi_report.post_process_data(multi_report_data)
    assert multi_data["organizations"] == [octopoes_api_connector.client, octopoes_api_connector_2.client]
    assert multi_data["tags"] == {
        "test1": ["test-test_multi_report", "test-test_multi_report-2"],
        "test2": ["test-test_multi_report-2"],
        "test3": ["test-test_multi_report-2"],
    }

    assert multi_data["basic_security_score"] == 100
    assert multi_data["total_critical_vulnerabilities"] == 0
    assert multi_data["total_findings"] == 6
    assert multi_data["total_systems"] == 4
    assert multi_data["total_hostnames"] == 14
    assert multi_data["service_counts"] == {"Mail": 2, "Web": 4, "Dicom": 2, "Other": 2}
    assert multi_data["open_ports"] == {
        "total": 4,
        "ports": {
            "80": {"open": 2, "services": {"http"}},
            "443": {"open": 2, "services": {"https"}},
            "22": {"open": 2, "services": {"ssh"}},
            "25": {"open": 2, "services": {"smtp"}},
        },
    }

    assert multi_data["asset_vulnerabilities"] == [
        {
            "asset": "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230",
            "vulnerabilities": {"CVE-2018-20677": None, "CVE-2019-8331": None, "RetireJS-jquerymigrate-f3a3": None},
            "organisation": "test-test_multi_report",
            "services": ["Web"],
        },
        {
            "asset": "IPAddressV4|test|192.0.2.3",
            "vulnerabilities": {"CVE-2018-20677": None, "CVE-2019-8331": None, "RetireJS-jquerymigrate-f3a3": None},
            "organisation": "test-test_multi_report",
            "services": ["Dicom", "Mail", "Other", "Web"],
        },
        {
            "asset": "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230",
            "vulnerabilities": {"CVE-2018-20677": None, "CVE-2019-8331": None, "RetireJS-jquerymigrate-f3a3": None},
            "organisation": "test-test_multi_report-2",
            "services": ["Web"],
        },
        {
            "asset": "IPAddressV4|test|192.0.2.3",
            "vulnerabilities": {"CVE-2018-20677": None, "CVE-2019-8331": None, "RetireJS-jquerymigrate-f3a3": None},
            "organisation": "test-test_multi_report-2",
            "services": ["Dicom", "Mail", "Other", "Web"],
        },
    ]
    assert multi_data["services"] == {
        "Mail": ["IPAddressV4|test|192.0.2.3", "IPAddressV4|test|192.0.2.3"],
        "Web": [
            "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230",
            "IPAddressV4|test|192.0.2.3",
            "IPAddressV6|test|3e4d:64a2:cb49:bd48:a1ba:def3:d15d:9230",
            "IPAddressV4|test|192.0.2.3",
        ],
        "Dicom": ["IPAddressV4|test|192.0.2.3", "IPAddressV4|test|192.0.2.3"],
        "Other": ["IPAddressV4|test|192.0.2.3", "IPAddressV4|test|192.0.2.3"],
    }
    assert multi_data["basic_security"]["summary"] == {
        "Mail": {
            "rpki": {"number_of_compliant": 2, "total": 2},
            "system_specific": {"number_of_compliant": 2, "total": 2},
            "safe_connections": {"number_of_compliant": 2, "total": 2},
        },
        "Web": {
            "rpki": {"number_of_compliant": 4, "total": 4},
            "system_specific": {"number_of_compliant": 4, "total": 4},
            "safe_connections": {"number_of_compliant": 4, "total": 4},
        },
        "Dicom": {
            "rpki": {"number_of_compliant": 2, "total": 2},
            "system_specific": {"number_of_compliant": 0, "total": 0},
            "safe_connections": {"number_of_compliant": 2, "total": 2},
        },
        "Other": {
            "rpki": {"number_of_compliant": 2, "total": 2},
            "system_specific": {"number_of_compliant": 0, "total": 0},
            "safe_connections": {"number_of_compliant": 2, "total": 2},
        },
    }
    assert multi_data["basic_security"]["safe_connections"] == {"number_of_available": 10, "number_of_ips": 10}
    assert multi_data["basic_security"]["system_specific"] == {
        "Dicom": {"checks": {}, "total": 0},
        "Mail": {"checks": {"DKIM": 2, "DMARC": 2, "SPF": 2}, "total": 2},
        "Other": {"checks": {}, "total": 0},
        "Web": {
            "checks": {
                "CSP Present": 4,
                "Certificate is not expired": 4,
                "Certificate is not expiring soon": 4,
                "Has a Security.txt": 4,
                "Has a certificate": 4,
                "No unnecessary ports open": 4,
                "Offers HTTPS": 4,
                "Redirects HTTP to HTTPS": 4,
                "Secure CSP Header": 4,
            },
            "total": 4,
        },
    }
    assert multi_data["basic_security"]["rpki"] == {
        "Dicom": {"number_of_available": 4, "number_of_ips": 4, "number_of_valid": 4, "rpki_ips": True},
        "Mail": {"number_of_available": 4, "number_of_ips": 4, "number_of_valid": 4, "rpki_ips": True},
        "Other": {"number_of_available": 4, "number_of_ips": 4, "number_of_valid": 4, "rpki_ips": True},
        "Web": {"number_of_available": 4, "number_of_ips": 4, "number_of_valid": 4, "rpki_ips": True},
    }
    assert multi_data["system_vulnerabilities"] == {
        "CVE-2018-20677": {"cvss": None, "Web": 4, "Dicom": 2, "Mail": 2, "Other": 2},
        "CVE-2019-8331": {"cvss": None, "Web": 4, "Dicom": 2, "Mail": 2, "Other": 2},
        "RetireJS-jquerymigrate-f3a3": {"cvss": None, "Web": 4, "Dicom": 2, "Mail": 2, "Other": 2},
    }
    assert multi_data["ipv6"] == {
        "Dicom": {"total": 2, "enabled": 2},
        "Mail": {"total": 2, "enabled": 2},
        "Other": {"total": 2, "enabled": 2},
        "Web": {"total": 2, "enabled": 2},
    }
    assert multi_data["recommendation_counts"] == {"Make sure there is a security.txt available.": 2}
