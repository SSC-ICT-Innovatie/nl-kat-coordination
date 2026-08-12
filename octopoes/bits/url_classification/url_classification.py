from collections.abc import Iterator
from ipaddress import IPv4Address, ip_address
from typing import Any

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6
from octopoes.models.ooi.web import URL, HostnameHTTPURL, IPAddressHTTPURL, WebScheme


def run(url: URL, additional_oois: list, config: dict[str, Any]) -> Iterator[OOI]:
    if url.raw.scheme == "http" or url.raw.scheme == "https":
        port = url.raw.port
        if port is None:
            if url.raw.scheme == "https":
                port = 443
            elif url.raw.scheme == "http":
                port = 80

        path = url.raw.path if url.raw.path is not None else "/"

        default_args = {"network": url.network, "scheme": WebScheme(url.raw.scheme), "port": port, "path": path}
        try:
            addr = ip_address(url.raw.host)
        except ValueError:
            hostname = Hostname(network=url.network, name=url.raw.host)
            hostname_url = HostnameHTTPURL(netloc=hostname.reference, **default_args)
            original_url = URL(network=url.network, raw=url.raw, web_url=hostname_url.reference)
            yield hostname
            yield hostname_url
            yield original_url
        else:
            if isinstance(addr, IPv4Address):
                ip = IPAddressV4(network=url.network, address=addr)
                ip_url = IPAddressHTTPURL(netloc=ip.reference, **default_args)
                original_url = URL(network=url.network, raw=url.raw, web_url=ip_url.reference)
                yield ip
                yield ip_url
                yield original_url
            else:
                ip = IPAddressV6(network=url.network, address=addr)
                ip_url = IPAddressHTTPURL(netloc=ip.reference, **default_args)
                original_url = URL(network=url.network, raw=url.raw, web_url=ip_url.reference)
                yield ip
                yield ip_url
                yield original_url
