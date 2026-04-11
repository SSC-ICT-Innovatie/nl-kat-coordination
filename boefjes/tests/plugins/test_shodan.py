import json

from boefjes.plugins.kat_shodan.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.network import IPPort, PortState, Protocol

input_ooi = {"primary_key": "IPAddressV4|internet|1.2.3.4", "network": {"name": "internet"}}


def test_shodan_normalizer_no_results():
    raw = json.dumps({}).encode()
    assert list(run(input_ooi, raw)) == []


def test_shodan_normalizer_results_without_data_key():
    raw = json.dumps({"ip_str": "1.2.3.4"}).encode()
    assert list(run(input_ooi, raw)) == []


def test_shodan_normalizer_open_ports_without_vulns():
    raw = json.dumps(
        {
            "data": [
                {"port": 80, "transport": "tcp"},
                {"port": 443, "transport": "tcp"},
                {"port": 53, "transport": "udp"},
            ]
        }
    ).encode()

    results = list(run(input_ooi, raw))

    ip_ports = [r for r in results if isinstance(r, IPPort)]
    assert len(ip_ports) == 3
    assert {(p.port, p.protocol) for p in ip_ports} == {(80, Protocol.TCP), (443, Protocol.TCP), (53, Protocol.UDP)}
    assert all(p.state == PortState.OPEN for p in ip_ports)
    assert all(p.address == Reference.from_str("IPAddressV4|internet|1.2.3.4") for p in ip_ports)


# NOTE: a test for the `vulns` code path is intentionally NOT added here.
# The current normalizer iterates `scan["vulns"].values()`, while the Shodan
# API returns `vulns` as a dict keyed by CVE id (with detail dicts as values).
# Adding a test for the buggy behaviour would ratify it. The fix and
# corresponding test are filed in a separate PR so this PR stays focused on
# new test coverage only.
