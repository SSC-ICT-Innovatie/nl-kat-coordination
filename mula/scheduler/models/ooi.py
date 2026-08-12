from enum import Enum

from pydantic import BaseModel


class MutationOperationType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class RunOn(Enum):
    CREATE = MutationOperationType.CREATE.value
    UPDATE = MutationOperationType.UPDATE.value


class ScanProfile(BaseModel):
    level: int
    reference: str
    scan_profile_type: str | None


class OOI(BaseModel):
    """Representation of "Object Of Interests" from Octopoes."""

    primary_key: str
    object_type: str
    scan_profile: ScanProfile


class ScanProfileMutation(BaseModel):
    operation: MutationOperationType
    primary_key: str
    value: OOI | None
    client_id: str
