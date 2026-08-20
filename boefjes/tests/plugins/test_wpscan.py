import json

from pydantic_core import to_jsonable_python

from boefjes.plugins.kat_wpscan.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import CVEFindingType, Finding, RiskLevelSeverity, WPVulnFindingType
from octopoes.models.ooi.network import Network
from octopoes.models.ooi.software import Software, SoftwareInstance
from octopoes.models.ooi.web import HostnameHTTPURL, WebScheme

# Build the normalizer input via the real serializer, exactly like
# scheduler_client.py does (boefje_meta.arguments["input"] = ooi.serialize()).
# This ensures the fixture can never drift from the production input shape.
_network = Network(name="internet")
_hostname = Hostname(network=_network.reference, name="example.com")
_url = HostnameHTTPURL(
    network=_network.reference, scheme=WebScheme.HTTPS, netloc=_hostname.reference, port=443, path="/"
)
_software = Software(name="WordPress", version="4.9.8")
_instance = SoftwareInstance(ooi=_url.reference, software=_software.reference)
input_ooi = json.loads(json.dumps(to_jsonable_python(_instance.serialize())))
URL_PK = str(_url.reference)


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


def test_wpscan_input_shape_matches_production_serializer():
    """The module-level input_ooi is built via SoftwareInstance.serialize(),
    exactly like scheduler_client.py:125. This pins the fixture to the
    production shape so the input-handling path can't silently drift."""
    assert input_ooi["object_type"] == "SoftwareInstance"
    assert input_ooi["primary_key"].startswith("SoftwareInstance|")
    # The serialized `ooi` field is a token tree, not a nested primary_key.
    assert "primary_key" not in input_ooi["ooi"]
    assert input_ooi["ooi"]["scheme"] == "https"
    assert input_ooi["ooi"]["netloc"]["name"] == "example.com"

    results = list(run(input_ooi, _wpscan_payload([])))

    instances = [si for si in results if isinstance(si, SoftwareInstance)]
    assert instances
    assert all(str(si.ooi) == URL_PK for si in instances)


def test_wpscan_runner_fallback_input_shape():
    """The local runner falls back to {"primary_key": ...} when arguments["input"]
    is absent (runner.py:36). The normalizer must handle this shape too."""
    fallback_input = {"primary_key": input_ooi["primary_key"]}

    results = list(run(fallback_input, _wpscan_payload([])))

    instances = [si for si in results if isinstance(si, SoftwareInstance)]
    assert instances
    assert all(str(si.ooi) == URL_PK for si in instances)


def test_wpscan_cvss_scalar_string():
    """wpscan_out_parse types cvss as a scalar string; handle both shapes."""
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {"id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", "title": "Scalar cvss bug", "cvss": "7.5"}
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    wpvuln_type = next(r for r in results if isinstance(r, WPVulnFindingType))
    assert wpvuln_type.risk_score == 7.5
    assert wpvuln_type.risk_severity == RiskLevelSeverity.HIGH


def test_wpscan_cvss_non_numeric_does_not_abort():
    """A non-numeric cvss score must not abort the entire normalizer run."""
    raw = json.dumps(
        {
            "version": {
                "number": "4.9.8",
                "vulnerabilities": [
                    {"id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "title": "Bad cvss bug", "cvss": {"score": "N/A"}}
                ],
            }
        }
    ).encode()

    results = list(run(input_ooi, raw))

    wpvuln_type = next(r for r in results if isinstance(r, WPVulnFindingType))
    assert wpvuln_type.risk_score is None
    assert wpvuln_type.risk_severity == RiskLevelSeverity.UNKNOWN
