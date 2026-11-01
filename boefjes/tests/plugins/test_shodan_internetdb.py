import json

from boefjes.plugins.kat_shodan_internetdb.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding
from octopoes.models.ooi.network import IPPort
from octopoes.models.ooi.software import Software

input_ooi = {"primary_key": "IPAddressV4|internet|1.2.3.4", "address": "1.2.3.4", "network": {"name": "internet"}}


def _raw(**overrides) -> bytes:
    result = {
        "cpes": ["cpe:/a:nginx:nginx:1.18.0"],
        "hostnames": ["example.com"],
        "ip": "1.2.3.4",
        "ports": [80, 443],
        "tags": [],
        "vulns": ["CVE-2021-1234"],
    }
    result.update(overrides)
    return json.dumps(result).encode()


def test_ports_are_emitted_as_ipports():
    oois = list(run(input_ooi, _raw()))

    ports = sorted(p.port for p in oois if isinstance(p, IPPort))
    assert ports == [80, 443]


def test_cdn_tag_no_longer_skips_the_rest():
    # A cdn-tagged IP used to yield only the Cloudflare cpe; hostnames, ports,
    # vulns and other cpes were dropped.
    oois = list(run(input_ooi, _raw(tags=["cdn"])))

    assert [p.port for p in oois if isinstance(p, IPPort)]
    assert any(isinstance(o, Hostname) for o in oois)
    assert any(isinstance(o, Finding) for o in oois)
    assert any(isinstance(o, Software) for o in oois)
