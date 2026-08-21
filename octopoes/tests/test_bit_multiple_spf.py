from bits.multiple_spf.multiple_spf import run

from octopoes.models import Reference
from octopoes.models.ooi.dns.records import DNSTXTRecord
from octopoes.models.ooi.dns.zone import Hostname

"""Tests to see if there are more than one SPF record on this hostname
If so, produces a Finding"""

HOST = Hostname(name="example.com", network=Reference.from_str("Network|internet"))


def _txt(value):
    return DNSTXTRecord(hostname=HOST.reference, value=value)


def _findings(records):
    return [r for r in run(HOST, records, {}) if r.object_type == "Finding"]


def test_multiple_spf_records_are_flagged():
    records = [_txt("v=spf1 include:_spf.google.com ~all"), _txt("v=spf1 ip4:1.1.1.1 -all")]
    assert len(_findings(records)) == 1


def test_single_spf_record_is_not_flagged():
    assert _findings([_txt("v=spf1 include:_spf.google.com ~all")]) == []


def test_bare_second_record_is_flagged():
    # RFC 7208 3.1: a bare "v=spf1" (version terminated by end-of-record) is a valid SPF record.
    records = [_txt("v=spf1 include:_spf.google.com ~all"), _txt("v=spf1")]
    assert len(_findings(records)) == 1


def test_multiple_spf_records_are_flagged_uppercase():
    """Test if we pick up mixed case SPF records"""
    records = [_txt("v=SPF1 include:_spf.google.com ~all"), _txt("v=spf1 ip4:1.1.1.1 -all")]
    assert len(_findings(records)) == 1
