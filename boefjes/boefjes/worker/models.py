import datetime
from enum import Enum
from functools import total_ordering
from typing import Literal

from croniter import croniter
from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator
from pydantic import BaseModel, Field, field_validator


# This makes the RunOn sortable when in a list. This is convenient for e.g. the RunOnDB.from_run_ons method, that now
# does not have to take the ordering of a boefje.run_on into account in its match statement. This is especially handy
# once we introduce more RunOn values such as DELETE.
@total_ordering
class RunOn(Enum):
    CREATE = "create"
    UPDATE = "update"

    def __lt__(self, other):
        return self.value < other.value


class Organisation(BaseModel):
    id: str
    name: str
    deduplicate: bool = True


class Plugin(BaseModel):
    id: str
    name: str
    version: str | None = None
    created: datetime.datetime | None = None
    description: str | None = None
    enabled: bool = False
    static: bool = True  # We need to differentiate between local and remote plugins to know which ones can be deleted

    def __str__(self):
        return f"{self.id}:{self.version}"


class Boefje(Plugin):
    type: Literal["boefje"] = "boefje"
    scan_level: int = 1
    consumes: set[str] = Field(default_factory=set)
    produces: set[str] = Field(default_factory=set)
    boefje_schema: dict | None = None
    cron: str | None = None
    interval: int | None = None
    run_on: list[RunOn] | None = None
    runnable_hash: str | None = None
    oci_image: str | None = None
    oci_arguments: list[str] = Field(default_factory=list)
    deduplicate: bool = True

    @field_validator("boefje_schema")
    @classmethod
    def json_schema_valid(cls, schema: dict) -> dict:
        if schema is not None:
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as e:
                raise ValueError("The schema field is not a valid JSON schema") from e

        return schema

    @field_validator("cron")
    @classmethod
    def cron_valid(cls, cron: str | None) -> str | None:
        if cron is not None:
            croniter(cron)  # Raises a ValueError

        return cron

    class Config:
        validate_assignment = True


class BoefjeConfig(BaseModel):
    id: int
    settings: dict
    enabled: bool
    boefje_id: str
    organisation_id: str

    # a list of BoefjeConfig from other orgs that matching this config
    duplicates: list["BoefjeConfig"] = Field(default_factory=list)


class Normalizer(Plugin):
    type: Literal["normalizer"] = "normalizer"
    consumes: list[str] = Field(default_factory=list)  # mime types (and/ or boefjes)
    produces: list[str] = Field(default_factory=list)  # oois
    enabled: bool = True


class Bit(Plugin):
    type: Literal["bit"] = "bit"
    consumes: str
    produces: list[str]
    parameters: list[str]  # ooi.relation-name
    enabled: bool = True


PluginType = Boefje | Normalizer | Bit


class PaginationParameters(BaseModel):
    offset: int = 0
    limit: int | None = None


class FilterParameters(BaseModel):
    q: str | None = None
    type: Literal["boefje", "normalizer", "bit"] | None = None
    ids: list[str] | None = None
    consumes: set[str] | None = None
    produces: set[str] | None = None
    state: bool | None = None
    scan_level: int = 0
    oci_image: str | None = None
