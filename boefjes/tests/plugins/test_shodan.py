import json

from boefjes.plugins.kat_shodan.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.findings import CVEFindingType, Finding
from octopoes.models.ooi.network import IPPort, PortState, Protocol
from octopoes.models.ooi.software import Software, SoftwareInstance

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


def test_shodan_normalizer_emits_cve_findings_for_vulns():
    # Shodan reports vulns as a dict keyed by CVE id with detail dicts as values.
    raw = json.dumps(
        {
            "data": [
                {
                    "port": 22,
                    "transport": "tcp",
                    "vulns": {
                        "CVE-2016-0777": {"summary": "OpenSSH info leak", "verified": False},
                        "CVE-2018-15473": {"summary": "OpenSSH user enumeration", "verified": False},
                    },
                }
            ]
        }
    ).encode()

    results = list(run(input_ooi, raw))

    finding_types = [r for r in results if isinstance(r, CVEFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    ip_ports = [r for r in results if isinstance(r, IPPort)]

    assert len(ip_ports) == 1
    assert ip_ports[0].port == 22
    assert {ft.id for ft in finding_types} == {"CVE-2016-0777", "CVE-2018-15473"}
    assert len(findings) == 2
    assert all(f.ooi == ip_ports[0].reference for f in findings)


def test_shodan_normalizer_empty_vulns_dict_emits_no_findings():
    raw = json.dumps({"data": [{"port": 22, "transport": "tcp", "vulns": {}}]}).encode()

    results = list(run(input_ooi, raw))

    assert [r for r in results if isinstance(r, Finding)] == []
    assert [r for r in results if isinstance(r, CVEFindingType)] == []


def test_shodan_normalizer_extracts_software():
    raw = json.dumps(
        {
            "data": [
                {
                    "port": 22,
                    "transport": "tcp",
                    "product": "OpenSSH",
                    "version": "8.4p1",
                    "cpe23": ["cpe:2.3:a:openbsd:openssh:8.4p1:*:*:*:*:*:*:*"],
                }
            ]
        }
    ).encode()

    results = list(run(input_ooi, raw))

    software = [r for r in results if isinstance(r, Software)]
    instances = [r for r in results if isinstance(r, SoftwareInstance)]
    ip_ports = [r for r in results if isinstance(r, IPPort)]
    assert len(software) == 1
    assert software[0].name == "OpenSSH"
    assert software[0].version == "8.4p1"
    assert software[0].cpe == "cpe:2.3:a:openbsd:openssh:8.4p1:*:*:*:*:*:*:*"
    assert len(instances) == 1
    assert instances[0].ooi == ip_ports[0].reference


def test_shodan_normalizer_no_software_without_product():
    raw = json.dumps({"data": [{"port": 80, "transport": "tcp"}]}).encode()

    results = list(run(input_ooi, raw))

    assert [r for r in results if isinstance(r, Software)] == []
