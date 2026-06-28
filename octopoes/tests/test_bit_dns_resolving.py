from bits.dns_resolving.dns_resolving import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSAAAARecord, DNSARecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6

NETWORK = Reference.from_str("Network|internet")


def test_dns_resolving_single_a_record():
    hostname = Hostname(name="example.com", network=NETWORK)
    ipv4 = IPAddressV4(address="1.2.3.4", network=NETWORK)
    a_record = DNSARecord(hostname=hostname.reference, address=ipv4.reference, value="1.2.3.4")

    results = list(run(hostname, [a_record], {}))

    assert len(results) == 1
    assert results[0].object_type == "ResolvedHostname"
    assert results[0].hostname == hostname.reference
    assert results[0].address == ipv4.reference


def test_dns_resolving_single_aaaa_record():
    hostname = Hostname(name="example.com", network=NETWORK)
    ipv6 = IPAddressV6(address="2001:db8::1", network=NETWORK)
    aaaa_record = DNSAAAARecord(hostname=hostname.reference, address=ipv6.reference, value="2001:db8::1")

    results = list(run(hostname, [aaaa_record], {}))

    assert len(results) == 1
    assert results[0].object_type == "ResolvedHostname"
    assert results[0].address == ipv6.reference


def test_dns_resolving_multiple_records_emit_one_resolved_per_record():
    hostname = Hostname(name="example.com", network=NETWORK)
    ipv4_a = IPAddressV4(address="1.2.3.4", network=NETWORK)
    ipv4_b = IPAddressV4(address="5.6.7.8", network=NETWORK)
    ipv6 = IPAddressV6(address="2001:db8::1", network=NETWORK)
    records = [
        DNSARecord(hostname=hostname.reference, address=ipv4_a.reference, value="1.2.3.4"),
        DNSARecord(hostname=hostname.reference, address=ipv4_b.reference, value="5.6.7.8"),
        DNSAAAARecord(hostname=hostname.reference, address=ipv6.reference, value="2001:db8::1"),
    ]

    results = list(run(hostname, records, {}))

    assert len(results) == 3
    assert {r.address for r in results} == {ipv4_a.reference, ipv4_b.reference, ipv6.reference}
    assert all(r.hostname == hostname.reference for r in results)


def test_dns_resolving_no_records_yields_nothing():
    hostname = Hostname(name="example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    assert results == []
