import json

from boefjes.plugins.kat_nuclei_take_over.normalize import run
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.web import URL

input_ooi = {"primary_key": "Hostname|internet|example.com"}


def test_two_takeovers_on_one_host_do_not_collapse():
    raw = "\n".join(
        [
            json.dumps({"matched-at": "https://blog.example.com", "info": {"name": "GitHub takeover"}}),
            json.dumps({"matched-at": "https://shop.example.com", "info": {"name": "S3 takeover"}}),
        ]
    ).encode()

    oois = list(run(input_ooi, raw))

    findings = [o for o in oois if isinstance(o, Finding)]
    assert len(findings) == 2
    assert len({f.ooi for f in findings}) == 2
    assert len([o for o in oois if isinstance(o, URL)]) == 2


def test_falls_back_to_hostname_without_matched_at():
    raw = json.dumps({"info": {"name": "GitHub takeover"}}).encode()

    oois = list(run(input_ooi, raw))

    findings = [o for o in oois if isinstance(o, Finding)]
    assert len(findings) == 1
    assert str(findings[0].ooi) == "Hostname|internet|example.com"
