from typing import Literal

from pydantic import field_validator

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Software(OOI):
    object_type: Literal["Software"] = "Software"

    name: str
    version: str | None = None
    cpe: str | None = None

    @field_validator("name", "version", "cpe", mode="before")
    @classmethod
    def coerce_numeric_to_string(cls, value: object) -> object:
        """Coerce a numeric version to a string.

        External APIs (e.g. shodan, censys, binaryedge) deliver numeric versions, which would
        otherwise fail field validation and abort the whole scan's normalization. Only numbers are
        coerced — a bool/list/dict is left for pydantic to reject, so a structurally wrong value
        surfaces as a normalizer bug instead of being stored as garbage. The reference-separator
        escaping (issue #5299) lives in OOI.natural_key, so it is not repeated here.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return str(value)
        return value

    _natural_key_attrs = ["name", "version", "cpe"]
    _information_value = ["name"]
    _traversable = False

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        version = reference.tokenized.version
        if version:
            version = f" {version}"
        return f"{reference.tokenized.name}{version}"


class SoftwareInstance(OOI):
    object_type: Literal["SoftwareInstance"] = "SoftwareInstance"

    ooi: Reference = ReferenceField(OOI, max_issue_scan_level=0, max_inherit_scan_level=1)
    software: Reference = ReferenceField(Software, max_issue_scan_level=1, max_inherit_scan_level=0)

    _natural_key_attrs = ["ooi", "software"]
    _reverse_relation_names = {"ooi": "software_instances", "software": "instances"}

    # PK example: SoftwareInstance|IPAddressV4|internet|1.1.1.1|Software|apache|1.0|apache:/a.2.1./asd/
    @property
    def natural_key(self) -> str:
        return f"{self.ooi}|{self.software}"

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|")
        ooi_reference = Reference.from_str("|".join(parts[0:-4]))
        software_reference = Reference.from_str("|".join(parts[-4:]))
        return f"{software_reference.human_readable} @ {ooi_reference.human_readable}"
