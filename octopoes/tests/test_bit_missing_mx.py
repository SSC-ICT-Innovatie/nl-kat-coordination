from bits.missing_mx.missing_mx import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import NXDOMAIN, DNSMXRecord
from octopoes.models.ooi.dns.zone import Hostname

NETWORK = Reference.from_str("Network|internet")


def _hostname(name):
    return Hostname(network=NETWORK, name=name)


def _mx(hostname, value="10 mail.example.com", preference=10):
    return DNSMXRecord(hostname=hostname.reference, dns_record_type="MX", value=value, preference=preference)


def _nxdomain(hostname):
    return NXDOMAIN(hostname=hostname.reference, dns_record_type="A", value="NXDOMAIN")


def _findings(hostname, additional):
    return [r for r in run(hostname, additional, {}) if r.object_type == "Finding"]


def test_domain_without_mx_flagged():
    host = _hostname("example.com")
    assert len(_findings(host, [])) == 1


def test_domain_with_mx_clean():
    host = _hostname("example.com")
    mx = _mx(host)
    assert _findings(host, [mx]) == []


def test_null_mx_not_flagged():
    host = _hostname("example.com")
    # The DNS normalizer stores MX value as "preference target" (e.g. "0 ."),
    # not just "." — the bit must parse the target part to detect a null MX.
    mx = _mx(host, value="0 .", preference=0)
    assert _findings(host, [mx]) == []


def test_subdomain_not_checked():
    host = _hostname("www.example.com")
    assert _findings(host, []) == []


def test_nxdomain_skipped():
    host = _hostname("example.com")
    nxd = _nxdomain(host)
    assert _findings(host, [nxd]) == []
