"""Parse a free-form "blob" of objects into OOI instances.

Users can paste a mix of IPv4/IPv6 addresses, subnets, hostnames and
URLs into a single field. Each entry is classified automatically:

1. A value with a scheme (``https://example.com/``) becomes a URL OOI.
2. A value in CIDR notation (``192.0.2.0/24``) becomes an IPV4NetBlock
   or IPV6NetBlock OOI (plus its start IP, a required relation).
3. A value that parses as an IP address becomes an IPAddressV4 or
   IPAddressV6 OOI.
4. Anything else must be a valid hostname (the Hostname model validates
   IDNA and the allowed character set) and becomes a Hostname OOI.
"""

import ipaddress
import re
from typing import NamedTuple

from pydantic import ValidationError

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, IPV4NetBlock, IPV6NetBlock, Network
from octopoes.models.ooi.web import URL

SEPARATOR_PATTERN = re.compile(r"[,\s]+")
SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class ParsedEntry(NamedTuple):
    """One valid value from the blob: source line, the OOI it maps to, and OOIs to declare alongside it."""

    line_number: int
    ooi: OOI
    dependencies: list[OOI]


def split_blob(text: str) -> list[tuple[int, str]]:
    """Split pasted text into ``(line_number, value)`` pairs.

    Values may be separated by newlines, commas or whitespace, so a
    single line can contain multiple values. Line numbers refer to the
    pasted text and are used to report invalid entries back to the user.
    """
    pairs: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for value in SEPARATOR_PATTERN.split(line.strip()):
            if value:
                pairs.append((line_number, value))
    return pairs


def classify_ooi(value: str, network: Network) -> tuple[OOI, list[OOI]]:
    """Build the OOI matching the value.

    Returns a ``(ooi, dependencies)`` tuple: ``ooi`` is the object the
    value represents, ``dependencies`` contains OOIs that must be
    declared alongside it (e.g. the start IP of a netblock). Raises
    ``ValueError``/``ValidationError`` if the value is invalid.
    """
    if SCHEME_PATTERN.match(value):
        return URL(raw=value, network=network.reference), []
    if "/" in value:
        # CIDR notation: a netblock plus its start IP (required relation).
        # A prefix equal to the address length (/32, /128) is a single
        # address; main's SubnetAddForm treats those as IP addresses.
        ip_network = ipaddress.ip_network(value, strict=False)
        if ip_network.prefixlen == ip_network.max_prefixlen:
            return classify_ooi(str(ip_network.network_address), network)
        if ip_network.version == 6:
            start_ip = IPAddressV6(address=str(ip_network.network_address), network=network.reference)
            return (
                IPV6NetBlock(network=network.reference, start_ip=start_ip.reference, mask=ip_network.prefixlen),
                [start_ip],
            )
        start_ip = IPAddressV4(address=str(ip_network.network_address), network=network.reference)
        return (
            IPV4NetBlock(network=network.reference, start_ip=start_ip.reference, mask=ip_network.prefixlen),
            [start_ip],
        )
    try:
        # Tolerate bracketed IPv6, the notation used in URLs (e.g. [2001:db8::1]).
        address = value.strip("[]")
        version = ipaddress.ip_address(address).version
    except ValueError:
        # Not an IP address: must be a valid hostname (pydantic validates).
        return Hostname(name=value, network=network.reference), []
    if version == 6:
        return IPAddressV6(address=address, network=network.reference), []
    return IPAddressV4(address=address, network=network.reference), []


def parse_ooi_blob(text: str, network_name: str = "internet") -> tuple[list[ParsedEntry], dict[int, str]]:
    """Parse pasted text into OOIs.

    Returns a ``(parsed, errors)`` tuple where ``parsed`` is a list of
    :class:`ParsedEntry` for every valid value, and ``errors`` maps the
    line number of every invalid value to an error message.
    """
    network = Network(name=network_name)
    parsed: list[ParsedEntry] = []
    errors: dict[int, str] = {}

    for line_number, value in split_blob(text):
        try:
            ooi, dependencies = classify_ooi(value, network)
            parsed.append(ParsedEntry(line_number=line_number, ooi=ooi, dependencies=dependencies))
        except (ValidationError, ValueError):
            errors[line_number] = _format_error(value)

    return parsed, errors


def _format_error(value: str) -> str:
    return f'"{value}" is not a valid IP address, subnet, hostname or URL'
