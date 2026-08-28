from bits.missing_spf.missing_spf import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import NXDOMAIN
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.email_security import DNSSPFRecord
from octopoes.models.ooi.findings import Finding, KATFindingType

NETWORK = Reference.from_str("Network|internet")


def test_missing_spf_yields_finding_when_no_record():
    hostname = Hostname(name="example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    finding_types = [r for r in results if isinstance(r, KATFindingType)]
    findings = [r for r in results if isinstance(r, Finding)]
    assert len(finding_types) == 1
    assert finding_types[0].id == "KAT-NO-SPF"
    assert len(findings) == 1
    assert findings[0].ooi == hostname.reference


def test_missing_spf_no_finding_when_record_present():
    hostname = Hostname(name="example.com", network=NETWORK)
    # DNSSPFRecord requires a dns_txt_record reference; use a synthetic one
    spf = DNSSPFRecord(
        dns_txt_record=Reference.from_str("DNSTXTRecord|internet|example.com|v=spf1 ~all"), value="v=spf1 ~all"
    )

    results = list(run(hostname, [spf], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_spf_no_finding_for_subdomain():
    hostname = Hostname(name="mail.example.com", network=NETWORK)

    results = list(run(hostname, [], {}))

    assert not [r for r in results if isinstance(r, Finding)]


def test_missing_spf_no_finding_when_nxdomain():
    hostname = Hostname(name="example.com", network=NETWORK)
    nxdomain = NXDOMAIN(hostname=hostname.reference)

    results = list(run(hostname, [nxdomain], {}))

    assert results == []
