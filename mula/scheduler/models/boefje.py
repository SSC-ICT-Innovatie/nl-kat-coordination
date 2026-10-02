import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Boefje(BaseModel):
    """Boefje representation."""

    id: str
    name: str | None = Field(default=None)
    version: str | None = Field(default=None)
    oci_image: str | None = None
    rate_limit_interval: float | None = Field(default=None, gt=0)
    rate_limit_group: str | None = None

    @model_validator(mode="after")
    def rate_limit_has_group(self):
        if self.rate_limit_interval is not None and not self.rate_limit_group:
            raise ValueError("rate_limit_group is required when rate_limit_interval is set")
        return self


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
