from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField

"""Identifiers are used on many contexts in the open web.
Some are API-keys, some are usernames or handles, and some might be account
numbers. Locating these identifiers in various resources, and finding their use
over different hostnames might provide correlation of shared resources on
various levels."""


class IdentifierVendor(OOI):
    """A party giving out identifiable tokens"""

    object_type: Literal["IdentifierVendor"] = "IdentifierVendor"
    name: str

    _natural_key_attrs = ["name"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Vendor of identifiers {reference.tokenized.name}"


class Identifier(OOI):
    """Eg, API-keys, account numbers, names that we can identify on the public web"""

    object_type: Literal["Identifier"] = "Identifier"
    vendor: Reference = ReferenceField(IdentifierVendor)
    value: str

    _reverse_relation_names = {"vendor": "identifiers"}

    @property
    def natural_key(self) -> str:
        return f"{str(self.vendor.name)}|{self.value}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Identifier {reference.tokenized.value} by {reference.tokenized.vendor.name}"


class IdentifierInstance(OOI):
    """An instance of an identifier tied to a specific OOI, telling us where
    this Identifier was spotted."""

    object_type: Literal["IdentifierInstance"] = "IdentifierInstance"
    identifier: Reference = ReferenceField(Identifier)
    location: Reference = ReferenceField(OOI)

    _reverse_relation_names = {"identifier": "locations", "location": "identifiers"}

    @property
    def natural_key(self) -> str:
        return f"{self.identifier.natural_key}|{self.location.natural_key}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|", 2)
        vendor = parts[0]
        identifier = parts[1]
        location = Reference.from_str(parts[2])
        return f"IdentifierInstance {identifier} by {vendor} @ {location.human_readable}"
