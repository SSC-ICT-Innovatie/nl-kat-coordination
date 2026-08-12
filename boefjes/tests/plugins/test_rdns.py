from boefjes.plugins.kat_rdns.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSPTRRecord
from octopoes.models.ooi.dns.zone import Hostname
from tests.loading import get_dummy_data

input_ooi = {"primary_key": "IPAddressV4|internet|192.0.2.1", "network": {"name": "internet"}}


def test_rdns_nxdomain():
    oois = set(run(input_ooi, get_dummy_data("rdns-nxdomain.txt")))

    assert not oois


returned_oois = {
    DNSPTRRecord(
        scan_profile=None,
        hostname=Reference("Hostname|internet|example.com"),
        dns_record_type="PTR",
        value="1.2.0.192.in-addr.arpa. 86400 IN PTR example.com.",
        ttl=86400,
        address=Reference("IPAddressV4|internet|192.0.2.1"),
    ),
    Hostname(
        object_type="Hostname",
        scan_profile=None,
        primary_key="Hostname|internet|example.com",
        network=Reference("Network|internet"),
        name="example.com",
        dns_zone=None,
        registered_domain=None,
    ),
}


def test_rdns_answer_1():
    oois = set(run(input_ooi, get_dummy_data("rdns-example1.txt")))

    assert oois == returned_oois


def test_rdns_answer_2():
    oois = set(run(input_ooi, get_dummy_data("rdns-example2.txt")))

    assert oois == returned_oois
