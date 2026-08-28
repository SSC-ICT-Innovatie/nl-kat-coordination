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
    _natural_key_attrs = ["vendor", "value"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"Identifier {reference.tokenized.value} by {reference.tokenized.vendor.name}"


class IdentifierInstance(OOI):
    """An instance of an identifier tied to a specific OOI, telling us where
    this Identifier was spotted."""

    object_type: Literal["IdentifierInstance"] = "IdentifierInstance"
    identifier: Reference = ReferenceField(Identifier)
    location: Reference = ReferenceField(OOI)

    _reverse_relation_names = {"identifier": "locations", "location": "identifier_sightings"}

    @property
    def natural_key(self) -> str:
        return f"{str(self.location)}|{self.identifier.natural_key}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        # The natural key is <full location reference>|<vendor name>|<value>, so
        # the identifier fields pop off the end and the remainder is the
        # location reference (the Finding convention for abstract references).
        parts = reference.natural_key.split("|")
        value = parts.pop()
        vendor_name = parts.pop()
        location = Reference.from_str("|".join(parts))
        return f"IdentifierInstance {value} by {vendor_name} @ {location.human_readable}"
