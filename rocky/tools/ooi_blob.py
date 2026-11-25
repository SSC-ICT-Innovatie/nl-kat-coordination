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
from tools.forms.subnet import MIN_SCANNABLE_PREFIXLEN_V4, MIN_SCANNABLE_PREFIXLEN_V6

SEPARATOR_PATTERN = re.compile(r"[,\s]+")
SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class ParsedEntry(NamedTuple):
    """One valid blob value: source line, original value, its OOI, and OOIs to declare alongside it."""

    line_number: int
    value: str
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


def parse_ooi_blob(text: str, network_name: str = "internet") -> tuple[list[ParsedEntry], dict[int, list[str]]]:
    """Parse pasted text into OOIs.

    Returns a ``(parsed, errors)`` tuple where ``parsed`` is a list of
    :class:`ParsedEntry` for every valid value, and ``errors`` maps the
    line number of each invalid value to its error message. A line can
    contain multiple values, so an error list per line may be longer
    than one.
    """
    network = Network(name=network_name)
    parsed: list[ParsedEntry] = []
    errors: dict[int, list[str]] = {}

    for line_number, value in split_blob(text):
        try:
            ooi, dependencies = classify_ooi(value, network)
            parsed.append(ParsedEntry(line_number=line_number, value=value, ooi=ooi, dependencies=dependencies))
        except (ValidationError, ValueError):
            errors.setdefault(line_number, []).append(_format_error(value))

    return parsed, errors


def subnet_notices(entries: list[ParsedEntry]) -> dict[int, dict]:
    """Build review-page notices for pasted subnets.

    Returns per-line info for entries whose input had host bits set
    (normalized to the subnet) and for ranges the nmap boefjes skip by
    default, mirroring the warnings of the dedicated subnet form.
    """
    notices: dict[int, dict] = {}
    for entry in entries:
        if entry.ooi.object_type not in ("IPV4NetBlock", "IPV6NetBlock"):
            continue
        is_v6 = entry.ooi.object_type == "IPV6NetBlock"
        ip_interface = ipaddress.ip_interface(f"{entry.ooi.start_ip.tokenized.address}/{entry.ooi.mask}")
        min_prefixlen = MIN_SCANNABLE_PREFIXLEN_V6 if is_v6 else MIN_SCANNABLE_PREFIXLEN_V4
        notices[entry.line_number] = {
            "normalized": entry.value.rstrip("/") != str(ip_interface.network),
            "network_address": str(ip_interface.network.network_address),
            "mask": entry.ooi.mask,
            "range_skipped_by_nmap": entry.ooi.mask < min_prefixlen,
            "min_scannable_prefixlen": min_prefixlen,
        }
    return notices


def _format_error(value: str) -> str:
    return f'"{value}" is not a valid IP address, subnet, hostname or URL'
