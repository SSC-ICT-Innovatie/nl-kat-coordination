from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class IdentifierVendor(OOI):
    object_type: Literal["IdentifierVendor"] = "IdentifierVendor"

    name: str
    _traversable = False


class Identifier(OOI):
    object_type: Literal["Identifier"] = "Identifier"

    vendor: Reference = ReferenceField(IdentifierVendor, max_issue_scan_level=0, max_inherit_scan_level=0)
    identifier: str

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"{reference.tokenized.vendor.name} / {reference.tokenized.identifier}"


class IdentifierUsage(OOI):
    object_type: Literal["IdentifierUsage"] = "IdentifierUsage"

    identifier: Reference = ReferenceField(Identifier, max_issue_scan_level=0, max_inherit_scan_level=0)
    usage: Reference = ReferenceField(OOI, max_issue_scan_level=0, max_inherit_scan_level=0)

    _natural_key_attrs = ["usage", "identifier"]

    @property
    def natural_key(self) -> str:
        return f"{self.usage}|{self.identifier}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        return f"""{reference.tokenized.identifier.vendor.name} / {reference.tokenized.identifier.identifier}
        as used on {reference.tokenized.usage}"""
