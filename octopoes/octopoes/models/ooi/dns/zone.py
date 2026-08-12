from __future__ import annotations

import string
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from octopoes.models import OOI, Reference
from octopoes.models.ooi.network import IPAddress, Network
from octopoes.models.persistence import ReferenceField

VALID_HOSTNAME_CHARACTERS = string.ascii_letters + string.digits + "-."


class DNSZone(OOI):
    """Represents the DNS zone.

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["DNSZone"] = "DNSZone"

    hostname: Reference = ReferenceField("Hostname", max_issue_scan_level=2, max_inherit_scan_level=1)
    parent: Reference | None = ReferenceField("DNSZone", max_issue_scan_level=0, max_inherit_scan_level=1, default=None)

    _natural_key_attrs = ["hostname"]

    _reverse_relation_names = {"parent": "child_dns_zones"}

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.hostname.name


class Hostname(OOI):
    """Represents the Hostname object.

    Example value
    -------------
    mispo.es
    """

    object_type: Literal["Hostname"] = "Hostname"

    network: Reference = ReferenceField(Network)
    name: Annotated[str, StringConstraints(to_lower=True)]

    dns_zone: Reference | None = ReferenceField(DNSZone, max_issue_scan_level=1, max_inherit_scan_level=2, default=None)

    registered_domain: Reference | None = ReferenceField(
        "Hostname", max_issue_scan_level=1, max_inherit_scan_level=2, default=None
    )

    _natural_key_attrs = ["network", "name"]

    _reverse_relation_names = {"network": "hostnames", "dns_zone": "hostnames", "registered_domain": "subdomains"}

    @field_validator("name")
    @classmethod
    def hostname_valid(cls, v: str) -> str:
        v = v.encode("idna").decode()

        for c in v:
            if c not in VALID_HOSTNAME_CHARACTERS:
                raise ValueError(f"Invalid hostname character: {c}")

        if v.endswith("-"):
            raise ValueError("Hostname must not end with a hyphen")

        return v

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return reference.tokenized.name


class ResolvedHostname(OOI):
    """Represents resolved hostnames.

    Example value
    -------------
    ns1.domaindiscount24.net -> 193.227.117.34
    """

    object_type: Literal["ResolvedHostname"] = "ResolvedHostname"

    hostname: Reference = ReferenceField(Hostname, max_issue_scan_level=0, max_inherit_scan_level=4)
    address: Reference = ReferenceField(IPAddress, max_issue_scan_level=4, max_inherit_scan_level=0)

    _natural_key_attrs = ["hostname", "address"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.hostname.name} -> {reference.tokenized.address.address}"
