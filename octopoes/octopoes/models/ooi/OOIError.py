from __future__ import annotations

from typing import Literal

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class OOIValidationError(OOI):
    """This object-type represents a placeholder OOI-like error container to signal
    to the user that parsing of a specific OOI failed"""

    object_type: Literal["OOIValidationError"] = "OOIValidationError"
    source: Reference = ReferenceField(OOI)
    message: str

    _natural_key_attrs = ["source"]
