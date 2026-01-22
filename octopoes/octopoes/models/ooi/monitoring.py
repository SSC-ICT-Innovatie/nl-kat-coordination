from __future__ import annotations

from typing import Literal

import yaml
from pydantic import JsonValue

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Application(OOI):
    """Represents Application objects."""

    object_type: Literal["Application"] = "Application"
    name: str

    _natural_key_attrs = ["name"]

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: Application) -> yaml.Node:
        return dumper.represent_mapping("!Application", {**cls.get_ooi_yml_repr_dict(data), "name": data.name})


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

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: Incident) -> yaml.Node:
        return dumper.represent_mapping(
            "!Incident",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "application": data.application,
                "event_id": data.event_id,
                "event_type": data.event_type,
                "event_title": data.event_title,
                "severity": data.severity,
                "meta_data": data.meta_data,
            },
        )
