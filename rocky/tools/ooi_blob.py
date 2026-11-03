"""Parse a free-form "blob" of objects into OOI instances.

Users can paste a mix of IPv4/IPv6 addresses, hostnames and URLs into a
single field. Each entry is classified automatically:

1. A value with a scheme (``https://example.com/``) becomes a URL OOI.
2. A value that parses as an IP address becomes an IPAddressV4 or
   IPAddressV6 OOI.
3. Anything else must be a valid hostname (the Hostname model validates
   IDNA and the allowed character set) and becomes a Hostname OOI.
"""

import ipaddress
import re
from typing import TypeVar

from pydantic import ValidationError

from octopoes.models import OOI
from octopoes.models.ooi.dns.zone import Hostname
from octopoes.models.ooi.network import IPAddressV4, IPAddressV6, Network
from octopoes.models.ooi.web import URL

SEPARATOR_PATTERN = re.compile(r"[,\s]+")
SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")

OOIType = TypeVar("OOIType", bound=OOI)


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


def classify_ooi(value: str, network: Network) -> OOI:
    """Build the OOI matching the value, raising ``ValueError``/``ValidationError`` if invalid."""
    if SCHEME_PATTERN.match(value):
        return URL(raw=value, network=network.reference)
    try:
        version = ipaddress.ip_address(value).version
    except ValueError:
        # Not an IP address: must be a valid hostname (pydantic validates).
        return Hostname(name=value, network=network.reference)
    if version == 6:
        return IPAddressV6(address=value, network=network.reference)
    return IPAddressV4(address=value, network=network.reference)


def parse_ooi_blob(text: str, network_name: str = "internet") -> tuple[list[tuple[int, OOI]], dict[int, str]]:
    """Parse pasted text into OOIs.

    Returns a ``(parsed, errors)`` tuple where ``parsed`` contains
    ``(line_number, ooi)`` pairs for every valid value, and ``errors``
    maps the line number of every invalid value to an error message.
    """
    network = Network(name=network_name)
    parsed: list[tuple[int, OOI]] = []
    errors: dict[int, str] = {}

    for line_number, value in split_blob(text):
        try:
            parsed.append((line_number, classify_ooi(value, network)))
        except (ValidationError, ValueError):
            errors[line_number] = _format_error(value)

    return parsed, errors


def _format_error(value: str) -> str:
    return f'"{value}" is not a valid IP address, hostname or URL'
