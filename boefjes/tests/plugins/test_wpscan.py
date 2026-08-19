import json

from boefjes.plugins.kat_wpscan.normalize import run
from octopoes.models.ooi.findings import CVEFindingType, Finding, RiskLevelSeverity, WPVulnFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance

# The boefje consumes SoftwareInstance, so the normalizer receives the
# serialized SoftwareInstance that triggered the scan — its `ooi` field is the
# scanned URL. Tests use this production shape so the input-handling path is
# exercised the same way the scheduler exercises it.
URL_PK = "HostnameHTTPURL|internet|https|example.com|443|/"
input_ooi = {
    "object_type": "SoftwareInstance",
    "primary_key": f"SoftwareInstance|{URL_PK}|Software|WordPress|4.9.8|",
    "ooi": {"primary_key": URL_PK},
    "software": {"name": "WordPress", "version": "4.9.8", "primary_key": "Software|WordPress|4.9.8|"},
}


def _wpscan_payload(vulnerabilities: list[dict]) -> bytes:
    return json.dumps(
        {
            "banner": {"description": "WordPress Security Scanner"},
            "target_url": "https://example.com/",
            "effective_url": "https://example.com/",
            "interesting_findings": [],
            "version": {"number": "4.9.8", "vulnerabilities": vulnerabilities},
        }
    ).encode()


def test_wpscan_normalizer_empty_input():
    assert list(run(input_ooi, b"")) == []


def test_wpscan_normalizer_no_vulnerabilities():
    raw = _wpscan_payload([])
    results = list(run(input_ooi, raw))
    assert [r for r in results if isinstance(r, Finding)] == []


def test_wpscan_normalizer_single_cve_finding():
    raw = _wpscan_payload([{"title": "Stored XSS", "references": {"cve": ["2018-12895"]}}])

    results = list(run(input_ooi, raw))

    finding_types = [r for r in results if isinstance(r, CVEFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert any(ft.id == "CVE-2018-12895" for ft in finding_types)
    assert any(f.finding_type.tokenized.id == "CVE-2018-12895" for f in findings)


def test_wpscan_normalizer_multiple_cve_findings():
    raw = _wpscan_payload(
        [
            {"title": "Vuln A", "references": {"cve": ["2019-9787"]}},
            {"title": "Vuln B", "references": {"cve": ["2019-16219"]}},
        ]
    )

    results = list(run(input_ooi, raw))

    cve_ids = {ft.id for ft in results if isinstance(ft, CVEFindingType)}
    assert "CVE-2019-9787" in cve_ids
    assert "CVE-2019-16219" in cve_ids


def test_wpscan_extracts_core_and_plugin_software():
    raw = json.dumps(
        {
            "version": {"number": "4.9.8", "vulnerabilities": []},
            "plugins": {
                "contact-form-7": {
                    "slug": "contact-form-7",
                    "version": {"number": "5.0.1"},
                    "outdated": True,
                    "vulnerabilities": [],
                }
            },
        }
    ).encode()

    results = list(run(input_ooi, raw))

    software = {(s.name, s.version) for s in results if isinstance(s, Software)}
    assert ("WordPress", "4.9.8") in software
    assert ("contact-form-7", "5.0.1") in software
    # The outdated flag is no longer surfaced as a finding by the normalizer;
    # staleness is derived from the graph by a BIT (see PR description).
    assert not [f for f in results if isinstance(f, Finding)]


def test_wpscan_surfaces_non_cve_vulnerability_as_wpvuln_finding():
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "title": "WPVulnDB-only bug",
                        "references": {
                            "url": ["https://wpscan.com/vulnerability/11111111-1111-1111-1111-111111111111"]
                        },
                    }
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    wpvuln_types = [r for r in results if isinstance(r, WPVulnFindingType)]
    assert len(wpvuln_types) == 1
    assert wpvuln_types[0].id == "11111111-1111-1111-1111-111111111111"
    assert wpvuln_types[0].description == "WPVulnDB-only bug"
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(findings) == 1
    assert findings[0].finding_type.tokenized.id == "11111111-1111-1111-1111-111111111111"


def test_wpscan_wpvuln_finding_type_hydrated_from_scan_json():
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "title": "Auth bypass",
                        "cvss": {"vector": "AV:N/AC:L/Au:N/C:P/I:P/A:P", "score": 7.5},
                        "references": {
                            "url": ["https://wpscan.com/vulnerability/22222222-2222-2222-2222-222222222222"]
                        },
                    }
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    wpvuln_type = next(r for r in results if isinstance(r, WPVulnFindingType))
    assert wpvuln_type.risk_score == 7.5
    assert wpvuln_type.risk_severity == RiskLevelSeverity.HIGH
    assert str(wpvuln_type.source) == "https://wpscan.com/vulnerability/22222222-2222-2222-2222-222222222222"


def test_wpscan_findings_bind_to_software():
    raw = _wpscan_payload([{"title": "Stored XSS", "references": {"cve": ["2018-12895"]}}])

    results = list(run(input_ooi, raw))

    software = [s for s in results if isinstance(s, Software)]
    findings = [f for f in results if isinstance(f, Finding)]
    assert software
    # The CVE finding is bound to the WordPress Software, not the SoftwareInstance
    # nor the raw URL — the vulnerability is a property of the software.
    assert all(f.ooi == software[0].reference for f in findings)


def test_wpscan_no_nested_software_instance():
    """The input is a SoftwareInstance; emitted SoftwareInstances must bind to
    the scanned URL, not to the input SoftwareInstance (no second-order nesting)."""
    raw = _wpscan_payload([])

    results = list(run(input_ooi, raw))

    instances = [si for si in results if isinstance(si, SoftwareInstance)]
    assert instances
    for si in instances:
        # The SoftwareInstance.ooi must be the URL, never the input SoftwareInstance.
        assert si.ooi != input_ooi["primary_key"]
        assert str(si.ooi) == URL_PK


def test_wpscan_non_cve_vulnerabilities_are_distinct():
    """Each wpscan vulnerability carries a unique WPVulnDB id, so N non-CVE
    vulnerabilities yield N distinct WPVulnFindingType instances and N distinct
    Findings — they do not collapse to a single Finding in Octopoes."""
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "title": "Bug A - auth bypass"},
                    {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "title": "Bug B - SQL injection"},
                    {"id": "cccccccc-cccc-cccc-cccc-cccccccccccc", "title": "Bug C - RCE"},
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    wpvuln_types = [r for r in results if isinstance(r, WPVulnFindingType)]
    findings = [f for f in results if isinstance(f, Finding)]
    assert len(wpvuln_types) == 3
    assert len(findings) == 3
    assert {ft.id for ft in wpvuln_types} == {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "cccccccc-cccc-cccc-cccc-cccccccccccc",
    }
    # Distinct finding types on the same OOI -> distinct Finding natural keys.
    assert len({f.natural_key for f in findings}) == 3


def test_wpscan_findings_fall_back_to_url_without_version():
    """When a component's version is not detected there is no Software, so
    findings bind to the scanned URL instead."""
    raw = json.dumps(
        {
            "version": None,
            "plugins": {
                "contact-form-7": {
                    "slug": "contact-form-7",
                    "version": None,
                    "vulnerabilities": [
                        {"id": "dddddddd-dddd-dddd-dddd-dddddddddddd", "title": "Version-independent bug"}
                    ],
                }
            },
        }
    ).encode()

    results = list(run(input_ooi, raw))

    findings = [f for f in results if isinstance(f, Finding)]
    assert findings
    assert all(str(f.ooi) == URL_PK for f in findings)
