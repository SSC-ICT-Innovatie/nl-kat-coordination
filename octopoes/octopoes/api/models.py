import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, Field

from octopoes.models import Reference
from octopoes.models.ooi.findings import Finding
from octopoes.models.types import ConcreteFindingTypeType, ConcreteOOIType, OOIType


class FindingsByOOIResponse(BaseModel):
    """Findings reachable from an OOI, with their associated finding types bundled in so the caller
    does not have to look them up separately."""

    findings: list[Finding]
    finding_types: list[Annotated[ConcreteFindingTypeType, Field(discriminator="object_type")]]


class ServiceHealth(BaseModel):
    service: str
    healthy: bool = False
    version: str | None = None
    additional: Any = None
    results: list["ServiceHealth"] = Field(default_factory=list)


ServiceHealth.model_rebuild()


class _BaseObservation(BaseModel):
    method: str
    source: Reference
    source_method: str | None
    result: list[OOIType]
    valid_time: AwareDatetime
    task_id: uuid.UUID


# Connector models (more generic)
class Observation(_BaseObservation):
    """Used by Octopoes Connector to describe request body"""

    result: list[OOIType]
    valid_time: datetime


class Declaration(BaseModel):
    """Used by Octopoes Connector to describe request body"""

    ooi: OOIType
    valid_time: datetime
    end_valid_time: datetime | None = None
    method: str | None = None
    source_method: str | None = None
    task_id: uuid.UUID | None = None


class Affirmation(BaseModel):
    """Used by Octopoes Connector to describe request body"""

    ooi: OOIType
    valid_time: datetime
    method: str | None = None
    source_method: str | None = None
    task_id: uuid.UUID | None = None


class ScanProfileDeclaration(BaseModel):
    reference: Reference
    level: int
    valid_time: datetime


ValidatedOOIType = Annotated[ConcreteOOIType, Field(discriminator="object_type")]


# API models (timezone validation and pydantic parsing)
class ValidatedObservation(_BaseObservation):
    """Used by Octopoes API to validate and parse correctly"""

    result: list[ValidatedOOIType]
    valid_time: AwareDatetime
    source_method: str | None = None


class ValidatedDeclaration(BaseModel):
    """Used by Octopoes API to validate and parse correctly"""

    ooi: ValidatedOOIType
    valid_time: AwareDatetime
    end_valid_time: AwareDatetime | None = None
    method: str | None = "manual"
    source_method: str | None = None
    task_id: uuid.UUID | None = Field(default_factory=uuid.uuid4)


class ValidatedAffirmation(BaseModel):
    """Used by Octopoes API to validate and parse correctly"""

    ooi: ValidatedOOIType
    valid_time: AwareDatetime
    method: str | None = "hydration"
    source_method: str | None = None
    task_id: uuid.UUID | None = Field(default_factory=uuid.uuid4)
