import json

from boefjes.plugins.kat_nuclei_exposed_panels.normalize import run
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.web import URL

input_ooi = {"primary_key": "Hostname|internet|example.com"}


def test_two_panels_on_one_host_do_not_collapse():
    raw = "\n".join(
        [
            json.dumps({"matched-at": "https://example.com/admin", "info": {"description": "Admin panel"}}),
            json.dumps({"matched-at": "https://example.com/phpmyadmin", "info": {"description": "phpMyAdmin"}}),
        ]
    ).encode()

    oois = list(run(input_ooi, raw))

    findings = [o for o in oois if isinstance(o, Finding)]
    urls = [o for o in oois if isinstance(o, URL)]
    # Two distinct match URLs -> two distinct Finding natural keys, no collapse.
    assert len(findings) == 2
    assert len({f.ooi for f in findings}) == 2
    assert {str(u.raw).rstrip("/") for u in urls} == {"https://example.com/admin", "https://example.com/phpmyadmin"}


def test_falls_back_to_hostname_without_matched_at():
    raw = json.dumps({"info": {"description": "Admin panel"}}).encode()

    oois = list(run(input_ooi, raw))

    findings = [o for o in oois if isinstance(o, Finding)]
    assert len(findings) == 1
    assert str(findings[0].ooi) == "Hostname|internet|example.com"
    assert not [o for o in oois if isinstance(o, URL)]
