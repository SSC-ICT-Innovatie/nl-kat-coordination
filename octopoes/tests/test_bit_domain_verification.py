from bits.domain_owner_verification.domain_owner_verification import run

from octopoes.models.ooi.dns.records import DNSNSRecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import Network


def test_verification_pending():
    network = Network(name="fake")
    hostname = Hostname(name="example.com", network=network.reference)
    ns_hostname = Hostname(name="ns1.registrant-verification.ispapi.net", network=network.reference)
    ns_record = DNSNSRecord(hostname=hostname.reference, name_server_hostname=ns_hostname.reference, value="x")
    results = list(run(ns_record, [], {}))

    assert len(results) == 2


def test_no_verification_pending():
    network = Network(name="fake")
    hostname = Hostname(name="example.com", network=network.reference)
    ns_hostname = Hostname(name="ns1.example.com", network=network.reference)
    ns_record = DNSNSRecord(hostname=hostname.reference, name_server_hostname=ns_hostname.reference, value="x")
    results = list(run(ns_record, [], {}))

    assert len(results) == 0
