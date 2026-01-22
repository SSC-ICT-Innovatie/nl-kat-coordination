from __future__ import annotations

from typing import Annotated, Literal

import yaml
from pydantic import Field

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class GeographicPoint(OOI):
    """Represents Geographic points that can be added to objects.

    Possible value
    --------------
    longitude, latitude

    Example value
    -------------
    13,37
    """

    object_type: Literal["GeographicPoint"] = "GeographicPoint"

    ooi: Reference = ReferenceField(OOI)

    longitude: Annotated[float, Field(strict=True, ge=-180.0, le=180.0)]
    latitude: Annotated[float, Field(strict=True, ge=-180.0, le=180.0)]

    @property
    def natural_key(self) -> str:
        return f"{str(self.ooi)}|{self.longitude}|{self.latitude}"

    @classmethod
    def yml_representer(cls, dumper: yaml.SafeDumper, data: GeographicPoint) -> yaml.Node:
        return dumper.represent_mapping(
            "!GeographicPoint",
            {
                **cls.get_ooi_yml_repr_dict(data),
                "ooi": data.ooi,
                "longitude": data.longitude,
                "latitude": data.latitude,
            },
        )
