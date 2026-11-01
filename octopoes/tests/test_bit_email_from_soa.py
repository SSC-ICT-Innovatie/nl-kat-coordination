from bits.email_from_soa.email_from_soa import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSSOARecord
from octopoes.models.ooi.dns.zone import Hostname


def test_email_from_soa_rname():
    host = Hostname(network=Reference.from_str("Network|internet"), name="example.com")
    soa = DNSSOARecord(
        hostname=host.reference,
        soa_hostname=host.reference,
        value="ns1.example.com. hostmaster.example.com. 1 7200 3600 1209600 3600",
        rname="hostmaster.example.com.",
    )
    results = list(run(soa, [], {}))
    pks = [r.primary_key for r in results]
    assert "EmailAddress|hostmaster|internet|example.com" in pks


def test_email_from_soa_without_rname_yields_no_email():
    host = Hostname(network=Reference.from_str("Network|internet"), name="example.com")
    soa = DNSSOARecord(hostname=host.reference, soa_hostname=host.reference, value="x")
    assert not [r for r in run(soa, [], {}) if r.object_type == "EmailAddress"]
