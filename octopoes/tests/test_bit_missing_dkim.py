from bits.missing_dkim.missing_dkim import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DKIMExists
from octopoes.models.ooi.findings import Finding, KATFindingType

NETWORK = Reference.from_str("Network|internet")


def test_missing_dkim_yields_finding_when_no_dkim_exists_object():
    hostname = Hostname(name="example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    finding_types = [r for r in results if isinstance(r, KATFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(finding_types) == 1
    assert finding_types[0].id == "KAT-NO-DKIM"
    assert len(findings) == 1
    assert findings[0].ooi == hostname.reference


def test_missing_dkim_no_finding_when_dkim_exists_present():
    hostname = Hostname(name="example.com", network=NETWORK)
    dkim = DKIMExists(hostname=hostname.reference)

    results = list(run(hostname, [dkim], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_dkim_no_finding_for_subdomain():
    hostname = Hostname(name="blog.example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_dkim_no_finding_when_nxdomain():
    hostname = Hostname(name="example.com", network=NETWORK)
    nxdomain = NXDOMAIN(hostname=hostname.reference)

    results = list(run(hostname, [nxdomain], {}))

    assert results == []
