from typing import Literal

from pydantic import JsonValue

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Application(OOI):
    """Represents Application objects."""

    object_type: Literal["Application"] = "Application"
    name: str

    _natural_key_attrs = ["name"]


class Incident(OOI):
    """Represents Incident objects.

    Can be used to document incidents.

    Possible values
    ---------------
    application, event_id, event_type, event_title, severity, meta_data
    """

    object_type: Literal["Incident"] = "Incident"

    application: Reference = ReferenceField(Application)
    event_id: str
    event_type: str
    event_title: str
    severity: str
    meta_data: dict[str, JsonValue]

    _natural_key_attrs = ["application", "event_id"]
