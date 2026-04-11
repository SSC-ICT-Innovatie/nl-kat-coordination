import json

from boefjes.plugins.kat_nuclei_cve.normalize import run
from octopoes.models.ooi.findings import CVEFindingType, Finding

input_ooi = {"primary_key": "URL|internet|https://example.com/"}


def _line(cve_id: str, description: str = "Test description", curl: str = "curl https://example.com/") -> bytes:
    return (
        json.dumps(
            {"info": {"classification": {"cve-id": [cve_id.lower()]}, "description": description}, "curl-command": curl}
        )
        + "\n"
    ).encode()


def test_nuclei_cve_normalizer_empty_input():
    assert list(run(input_ooi, b"")) == []


def test_nuclei_cve_normalizer_single_finding():
    raw = _line("cve-2021-44228", "Log4Shell RCE", "curl 'https://example.com/${jndi:ldap://x}'")

    results = list(run(input_ooi, raw))

    finding_types = [r for r in results if isinstance(r, CVEFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(finding_types) == 1
    assert finding_types[0].id == "CVE-2021-44228"
    assert len(findings) == 1
    assert findings[0].description == "Log4Shell RCE"
    assert findings[0].proof == "curl 'https://example.com/${jndi:ldap://x}'"


def test_nuclei_cve_normalizer_multiple_findings_one_per_line():
    raw = _line("cve-2021-44228", "Log4Shell") + _line("cve-2017-5638", "Struts RCE")

    results = list(run(input_ooi, raw))

    finding_types = [r for r in results if isinstance(r, CVEFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert {ft.id for ft in finding_types} == {"CVE-2021-44228", "CVE-2017-5638"}
    assert len(findings) == 2
    assert {f.description for f in findings} == {"Log4Shell", "Struts RCE"}


def test_nuclei_cve_normalizer_uppercases_cve_id():
    # Source data sometimes has lowercase CVE IDs; the normalizer should normalize them.
    raw = _line("cve-2024-12345")

    results = list(run(input_ooi, raw))
    finding_types = [r for r in results if isinstance(r, CVEFindingType)]

    assert finding_types[0].id == "CVE-2024-12345"
