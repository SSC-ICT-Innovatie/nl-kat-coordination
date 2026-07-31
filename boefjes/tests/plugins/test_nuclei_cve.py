import json

from boefjes.plugins.kat_nuclei_cve.normalize import run
from octopoes.models.ooi.findings import CVEFindingType, Finding

INPUT_OOI = {"primary_key": "Hostname|internet|example.com"}


def _raw(*objs: dict) -> bytes:
    return "\n".join(json.dumps(o) for o in objs).encode()


def test_no_raw_yields_nothing():
    assert list(run(INPUT_OOI, b"")) == []


def test_valid_cve_line():
    raw = _raw(
        {
            "template-id": "CVE-2021-44228",
            "info": {"description": "Log4Shell", "classification": {"cve-id": ["cve-2021-44228"]}},
            "curl-command": "curl ...",
        }
    )
    out = list(run(INPUT_OOI, raw))
    finding_types = [o for o in out if isinstance(o, CVEFindingType)]
    findings = [o for o in out if isinstance(o, Finding)]

    assert [ft.id for ft in finding_types] == ["CVE-2021-44228"]
    assert len(findings) == 1
    assert findings[0].description == "Log4Shell"
    assert findings[0].proof == "curl ..."


def test_missing_description_does_not_crash():
    # Regression: a CVE template without info.description used to raise KeyError and
    # abort the whole task. It must now still yield the finding with description=None.
    raw = _raw({"template-id": "CVE-2023-1234", "info": {"classification": {"cve-id": ["CVE-2023-1234"]}}})

    findings = [o for o in run(INPUT_OOI, raw) if isinstance(o, Finding)]

    assert len(findings) == 1
    assert findings[0].description is None
    assert findings[0].proof is None


def test_lines_without_cve_id_are_skipped():
    raw = _raw(
        {"template-id": "x", "info": {"classification": {"cve-id": None}}},
        {"template-id": "y", "info": {"name": "no classification at all"}},
    )
    assert list(run(INPUT_OOI, raw)) == []


def test_one_bad_line_does_not_drop_valid_findings():
    raw = b"\n".join(
        [
            b"not json at all",
            json.dumps({"template-id": "z", "info": {"classification": {"cve-id": None}}}).encode(),
            json.dumps(
                {
                    "template-id": "CVE-2021-44228",
                    "info": {"description": "Log4Shell", "classification": {"cve-id": ["CVE-2021-44228"]}},
                    "curl-command": "curl ...",
                }
            ).encode(),
        ]
    )

    finding_types = [o for o in run(INPUT_OOI, raw) if isinstance(o, CVEFindingType)]

    assert [ft.id for ft in finding_types] == ["CVE-2021-44228"]
