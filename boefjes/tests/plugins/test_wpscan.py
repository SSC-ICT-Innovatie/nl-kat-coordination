import json

from boefjes.plugins.kat_wpscan.normalize import run
from octopoes.models.ooi.findings import CVEFindingType, Finding, KATFindingType
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


def test_wpscan_aggregates_non_cve_vulnerabilities():
    """Multiple non-CVE vulnerabilities on one component share one finding type
    and one OOI, so they collapse to one Finding in Octopoes. The normalizer
    must aggregate them deliberately — one finding carrying the count and all
    titles — instead of emitting N findings that silently collapse."""
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {"title": "Bug A - auth bypass", "references": {"url": ["https://wpscan.com/a"]}},
                    {"title": "Bug B - SQL injection", "references": {"url": ["https://wpscan.com/b"]}},
                    {"title": "Bug C - RCE", "references": {"url": ["https://wpscan.com/c"]}},
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    vuln_findings = [
        f for f in results if isinstance(f, Finding) and f.finding_type.tokenized.id == "KAT-VULNERABLE-SOFTWARE-VERSION"
    ]
    assert len(vuln_findings) == 1
    description = vuln_findings[0].description
    assert description.startswith("3 known vulnerabilities without CVE:")
    assert "Bug A - auth bypass" in description
    assert "Bug B - SQL injection" in description
    assert "Bug C - RCE" in description


def test_wpscan_flags_outdated_core_via_status():
    """WordPress core reports staleness through `status` ("insecure"/"outdated"),
    not the `outdated` boolean plugins/themes use."""
    raw = json.dumps(
        {"version": {"number": "4.9.8", "status": "insecure", "vulnerabilities": []}}
    ).encode()

    results = list(run(input_ooi, raw))

    outdated_findings = [
        f for f in results if isinstance(f, Finding) and f.finding_type.tokenized.id == "KAT-OUTDATED-SOFTWARE"
    ]
    assert len(outdated_findings) == 1
    assert "WordPress 4.9.8 is outdated." == outdated_findings[0].description
