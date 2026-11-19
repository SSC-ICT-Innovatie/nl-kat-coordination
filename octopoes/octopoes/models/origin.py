from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from octopoes.models import Reference


class OriginType(Enum):
    DECLARATION = "declaration"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    AFFIRMATION = "affirmation"


class Origin(BaseModel):
    origin_type: OriginType
    method: str
    source: Reference
    source_method: str | None = None  # None for bits and normalizers
    raw_file: str | None = None  # Name of the raw file the method consumed, if applicable
    result: list[Reference] = Field(default_factory=list)
    task_id: UUID | None = None

    def __sub__(self, other: Origin) -> set[Reference]:
        if isinstance(other, Origin):
            return set(self.result) - set(other.result)
        else:
            return NotImplemented

    @property
    def id(self) -> str:
        parts = [self.__class__.__name__, self.origin_type.value, self.method]
        if self.source_method is not None:
            parts.append(self.source_method)
        if self.raw_file is not None:
            parts.append(self.raw_file)
        parts.append(str(self.source))
        return "|".join(parts)

    def __eq__(self, other):
        if isinstance(other, Origin):
            return (
                self.origin_type == other.origin_type
                and self.method == other.method
                and self.source_method == other.source_method
                and self.raw_file == other.raw_file
                and self.source == other.source
                and set(self.result) == set(other.result)
            )
        return False


class OriginParameter(BaseModel):
    origin_id: str
    reference: Reference

    @property
    def id(self) -> str:
        return f"{self.__class__.__name__}|{self.origin_id}|{self.reference}"
