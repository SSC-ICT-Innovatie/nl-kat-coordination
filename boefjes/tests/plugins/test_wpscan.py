import json

from boefjes.plugins.kat_wpscan.normalize import run
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType
from octopoes.models.ooi.software import Software, SoftwareInstance

input_ooi = {"primary_key": "HostnameHTTPURL|internet|https|example.com|443|/"}


def _wpscan_payload(vulnerabilities: list[dict]) -> bytes:
    return json.dumps(
        {
            "banner": {"description": "WordPress Security Scanner"},
            "target_url": "https://example.com/",
            "effective_url": "https://example.com/",
            "interesting_findings": [],
            "version": {"number": "4.9.8", "status": "insecure", "vulnerabilities": vulnerabilities},
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
    # The outdated plugin yields a KAT-OUTDATED-SOFTWARE finding.
    assert "KAT-OUTDATED-SOFTWARE" in {ft.id for ft in results if isinstance(ft, KATFindingType)}


def test_wpscan_surfaces_non_cve_vulnerability():
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [{"title": "WPVulnDB-only bug", "references": {"url": ["https://wpscan.com/x"]}}],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    assert "KAT-VULNERABLE-SOFTWARE-VERSION" in {ft.id for ft in results if isinstance(ft, KATFindingType)}
    assert [f for f in results if isinstance(f, Finding)]


def test_wpscan_findings_bind_to_software_instance():
    raw = _wpscan_payload([{"title": "Stored XSS", "references": {"cve": ["2018-12895"]}}])

    results = list(run(input_ooi, raw))

    instances = [si for si in results if isinstance(si, SoftwareInstance)]
    findings = [f for f in results if isinstance(f, Finding)]
    assert instances
    # The CVE finding is bound to the WordPress SoftwareInstance, not the raw URL.
    assert any(f.ooi == instances[0].reference for f in findings)
