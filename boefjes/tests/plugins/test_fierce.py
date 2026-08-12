from ipaddress import IPv4Address, IPv6Address
from unittest.mock import MagicMock

from boefjes.plugins.kat_fierce.normalize import run
from octopoes.models import Reference
from octopoes.models.ooi.dns.zone import Hostname, ResolvedHostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from tests.loading import get_dummy_data


def test_fierce():
    oois = set(run(MagicMock(), get_dummy_data("inputs/fierce-result-example.com.json")))

    expected = {
        ResolvedHostname(
            hostname=Reference("Hostname|internet|www.example.com"), address=Reference("IPAddressV4|internet|192.0.2.2")
        ),
        ResolvedHostname(
            hostname=Reference("Hostname|internet|subdomain.example.com"),
            address=Reference("IPAddressV4|internet|192.0.2.3"),
        ),
        ResolvedHostname(
            hostname=Reference("Hostname|internet|ipv6.example.com"), address=Reference("IPAddressV6|internet|ff02::1")
        ),
        Hostname(network=Reference("Network|internet"), name="example.com"),
        Hostname(
            registered_domain=Reference("Hostname|internet|example.com"),
            network=Reference("Network|internet"),
            name="www.example.com",
        ),
        Hostname(
            registered_domain=Reference("Hostname|internet|example.com"),
            network=Reference("Network|internet"),
            name="subdomain.example.com",
        ),
        Hostname(
            registered_domain=Reference("Hostname|internet|example.com"),
            network=Reference("Network|internet"),
            name="ipv6.example.com",
        ),
        IPAddressV4(address=IPv4Address("192.0.2.3"), network=Reference("Network|internet")),
        IPAddressV4(address=IPv4Address("192.0.2.2"), network=Reference("Network|internet")),
        IPAddressV6(address=IPv6Address("ff02::1"), network=Reference("Network|internet")),
        Network(name="internet"),
    }

    assert oois == expected
