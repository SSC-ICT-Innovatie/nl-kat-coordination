from importlib import import_module

import pytest
from bits.definitions import get_bit_definitions
from bits.dns_caa_parsing.dns_caa_parsing import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import CAATAGS, DNSCAAAccountURI, DNSCAARecord
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.findings import Finding


def _caa(tag: CAATAGS, value: str) -> DNSCAARecord:
    host = Hostname(network=Reference.from_str("Network|internet"), name="example.com")
    return DNSCAARecord(hostname=host.reference, flags=0, tag=tag, value=value)


@pytest.mark.parametrize("bit_id", sorted(get_bit_definitions()))
def test_bit_module_is_importable(bit_id):
    import_module(get_bit_definitions()[bit_id].module)


def test_caa_account_uris_have_distinct_primary_keys():
    first = DNSCAAAccountURI(uri="https://acme-v02.api.letsencrypt.org/acme/acct/1")
    second = DNSCAAAccountURI(uri="https://acme-v02.api.letsencrypt.org/acme/acct/2")

    assert first.primary_key != second.primary_key


def test_caa_iodef_mailto_yields_email_address():
    results = list(run(_caa(CAATAGS.IODEF, "mailto:security@example.com"), [], {}))
    pks = [r.primary_key for r in results]

    assert "EmailAddress|security|internet|example.com" in pks
    assert not [r for r in results if isinstance(r, Finding)]


def test_caa_iodef_unsupported_scheme_yields_finding():
    results = list(run(_caa(CAATAGS.IODEF, "ftp://example.com"), [], {}))

    findings = [r for r in results if isinstance(r, Finding)]
    assert len(findings) == 1
    assert findings[0].finding_type == Reference.from_str("KATFindingType|KAT-CAA-IODEF")


def test_caa_issue_accounturi_links_account_uri():
    uri = "https://acme-v02.api.letsencrypt.org/acme/acct/1"
    results = list(run(_caa(CAATAGS.ISSUE, f"letsencrypt.org; accounturi={uri}"), [], {}))

    account_uri = next(r for r in results if isinstance(r, DNSCAAAccountURI))
    record = next(r for r in results if isinstance(r, DNSCAARecord))
    assert account_uri.uri == uri
    assert record.accounturi == account_uri.reference


def test_caa_issue_multiple_accounturi_yields_finding():
    results = list(run(_caa(CAATAGS.ISSUE, "letsencrypt.org; accounturi=https://a/1; accounturi=https://a/2"), [], {}))

    findings = [r for r in results if isinstance(r, Finding)]
    assert len(findings) == 1
    assert findings[0].finding_type == Reference.from_str("KATFindingType|KAT-CAA-ACCOUNTURI")
