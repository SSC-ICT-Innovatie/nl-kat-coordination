from typing import Literal

from pydantic import JsonValue

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Config(OOI):
    """Represents Config objects used for specifying organisation specific policies."""

    object_type: Literal["Config"] = "Config"

    ooi: Reference = ReferenceField(OOI)
    bit_id: str
    config: dict[str, JsonValue]

    _natural_key_attrs = ["ooi", "bit_id"]

    @classmethod
    def format_reference_human_readable(cls, reference: Reference) -> str:
        parts = reference.natural_key.split("|")
        ooi_reference = Reference.from_str("|".join(parts[:-1]))
        return f"Config of {parts[-1]} under {ooi_reference}"
