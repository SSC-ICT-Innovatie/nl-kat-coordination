import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Boefje(BaseModel):
    """Boefje representation."""

    id: str
    name: str | None = Field(default=None)
    version: str | None = Field(default=None)
    oci_image: str | None = None


class BoefjeMeta(BaseModel):
    """BoefjeMeta is the response object returned by the Bytes API"""

    id: uuid.UUID
    boefje: Boefje
    input_ooi: str | None
    arguments: dict[str, Any] = Field(default_factory=dict)
    organization: str

    started_at: datetime.datetime | None
    ended_at: datetime.datetime | None


class BoefjeConfig(BaseModel):
    """BoefjeConfig is the configuration object for a Boefje"""

    id: int
    boefje_id: str
    enabled: bool
    organisation_id: str
    settings: dict
    duplicates: list["BoefjeConfig"] = Field(default_factory=list)
