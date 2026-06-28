from bits.missing_dmarc.missing_dmarc import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DMARCTXTRecord
from octopoes.models.ooi.findings import Finding, KATFindingType

NETWORK = Reference.from_str("Network|internet")


def test_missing_dmarc_yields_finding_when_no_record():
    hostname = Hostname(name="example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    finding_types = [r for r in results if isinstance(r, KATFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(finding_types) == 1
    assert finding_types[0].id == "KAT-NO-DMARC"
    assert len(findings) == 1
    assert findings[0].ooi == hostname.reference


def test_missing_dmarc_no_finding_when_record_present():
    hostname = Hostname(name="example.com", network=NETWORK)
    dmarc = DMARCTXTRecord(hostname=hostname.reference, value="v=DMARC1;p=none;rua=mailto:dmarc@example.com", ttl=3600)

    results = list(run(hostname, [dmarc], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_dmarc_no_finding_for_subdomain():
    # bit should only report on apex domains, not subdomains like www.example.com
    hostname = Hostname(name="www.example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_dmarc_no_finding_when_nxdomain():
    hostname = Hostname(name="example.com", network=NETWORK)
    nxdomain = NXDOMAIN(hostname=hostname.reference)

    results = list(run(hostname, [nxdomain], {}))

    assert results == []
