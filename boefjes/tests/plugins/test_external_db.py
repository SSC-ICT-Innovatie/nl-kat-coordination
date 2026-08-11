import json

from boefjes.plugins.kat_external_db.normalize import run
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4

input_ooi = {"name": "internet"}


def test_external_db_imports_ip_addresses_when_domains_missing():
    # A response with only ip_addresses used to raise KeyError on the domains
    # loop, discarding every IP already yielded (the runner materializes the
    # generator). The IPs must survive.
    raw = json.dumps({"ip_addresses": [{"address": "1.2.3.4"}]}).encode()

    oois = list(run(input_ooi, raw))

    assert any(isinstance(o, IPAddressV4) and str(o.address) == "1.2.3.4" for o in oois)


def test_external_db_imports_domains_when_ip_addresses_missing():
    # A response with only domains used to raise KeyError on the ip_addresses
    # loop before any domain was reached, yielding nothing at all.
    raw = json.dumps({"domains": [{"name": "example.com"}]}).encode()

    oois = list(run(input_ooi, raw))

    assert any(isinstance(o, Hostname) and o.name == "example.com" for o in oois)


def test_external_db_imports_both_sections():
    raw = json.dumps({"ip_addresses": [{"address": "1.2.3.4"}], "domains": [{"name": "example.com"}]}).encode()

    oois = list(run(input_ooi, raw))

    assert any(isinstance(o, IPAddressV4) for o in oois)
    assert any(isinstance(o, Hostname) for o in oois)
