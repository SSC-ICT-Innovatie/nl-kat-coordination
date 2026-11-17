from bits.hostname_service_discovery.hostname_service_discovery import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPPort, Protocol
from octopoes.models.ooi.service import HostnameIPService, IPService, Service

NETWORK = Reference.from_str("Network|internet")


def _ip_address(address: str) -> IPAddressV4:
    return IPAddressV4(address=address, network=NETWORK)


def _service_at(address: str, port: int, service_name: str) -> IPService:
    ip_address = _ip_address(address)
    ip_port = IPPort(address=ip_address.reference, protocol=Protocol.TCP, port=port)
    return IPService(ip_port=ip_port.reference, service=Service(name=service_name).reference)


def _resolved_hostname(name: str, address: str) -> ResolvedHostname:
    hostname = Hostname(name=name, network=NETWORK)
    ip_address = _ip_address(address)
    return ResolvedHostname(hostname=hostname.reference, address=ip_address.reference)


def test_discovery_links_matching_service_and_hostname():
    ip_address = _ip_address("192.0.2.10")
    https = _service_at("192.0.2.10", 443, "https")
    ssh = _service_at("192.0.2.10", 22, "ssh")
    resolved = _resolved_hostname("example.com", "192.0.2.10")

    results = list(run(ip_address, [https, ssh, resolved], {}))

    assert len(results) == 2
    assert {r.ip_service for r in results} == {https.reference, ssh.reference}
    assert all(r.hostname == resolved.hostname for r in results)
    assert all(isinstance(r, HostnameIPService) for r in results)


def test_discovery_links_multiple_hostnames():
    ip_address = _ip_address("192.0.2.10")
    https = _service_at("192.0.2.10", 443, "https")
    resolved_a = _resolved_hostname("a.example.com", "192.0.2.10")
    resolved_b = _resolved_hostname("b.example.com", "192.0.2.10")

    results = list(run(ip_address, [https, resolved_a, resolved_b], {}))

    assert len(results) == 2
    assert {r.hostname.tokenized.name for r in results} == {"a.example.com", "b.example.com"}


def test_discovery_with_only_one_side_yields_nothing():
    """Without both a service and a resolved hostname, there is nothing to link."""
    ip_address = _ip_address("192.0.2.10")
    https = _service_at("192.0.2.10", 443, "https")
    resolved = _resolved_hostname("example.com", "192.0.2.10")

    assert list(run(ip_address, [https], {})) == []
    assert list(run(ip_address, [resolved], {})) == []


def test_discovery_is_idempotent():
    """Re-running with the same inputs yields the identical OOI; dedup happens
    via the natural key when saved."""
    ip_address = _ip_address("192.0.2.10")
    https = _service_at("192.0.2.10", 443, "https")
    resolved = _resolved_hostname("example.com", "192.0.2.10")

    first = list(run(ip_address, [https, resolved], {}))
    second = list(run(ip_address, [https, resolved], {}))

    assert first == second
    assert first[0].primary_key == "HostnameIPService|internet|192.0.2.10|tcp|443|https|internet|example.com"


def test_discovery_handles_ipv6():
    network = Reference.from_str("Network|internet")
    ip_address = IPAddressV6(address="2001:db8::10", network=network)

    ip_port = IPPort(address=ip_address.reference, protocol=Protocol.TCP, port=443)
    ip_service = IPService(ip_port=ip_port.reference, service=Service(name="https").reference)
    hostname = Hostname(name="example.com", network=network)
    resolved = ResolvedHostname(hostname=hostname.reference, address=ip_address.reference)

    results = list(run(ip_address, [ip_service, resolved], {}))

    assert len(results) == 1
    assert results[0].primary_key == ("HostnameIPService|internet|2001:db8::10|tcp|443|https|internet|example.com")
