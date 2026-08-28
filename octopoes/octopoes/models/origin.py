from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from octopoes.models import Reference
from octopoes.models.types import OOIType


class OriginType(Enum):
    DECLARATION = "declaration"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    AFFIRMATION = "affirmation"
    NIBBLET = "nibblet"


class Origin(BaseModel):
    origin_type: OriginType
    method: str
    source: Reference | None
    source_method: str | None = None  # None for bits and normalizers
    result: list[Reference] = Field(default_factory=list)
    phantom_result: list[OOIType] | None = None  # None for anything other than nibblet
    parameters_hash: str | None = None  # None for anything other than nibblet
    parameters_references: list[Reference | None] | None = None  # None for anything other than nibblet
    optional_references: list[Reference | None] | None = None  # None for anything other than nibblet
    task_id: UUID | None = None

    def __sub__(self, other: Origin) -> set[Reference]:
        if isinstance(other, Origin):
            return set(self.result) - set(other.result)
        else:
            return NotImplemented

    @property
    def id(self) -> str:
        if self.origin_type == OriginType.NIBBLET:
            return "|".join(
                map(
                    str,
                    [
                        self.__class__.__name__,
                        self.origin_type.value,
                        self.method,
                        f"[{','.join(sorted([str(param) for param in self.parameters_references]))}]"
                        if self.parameters_references is not None
                        else "Null",
                    ],
                )
            )
        elif self.source_method is not None:
            return (
                f"{self.__class__.__name__}|{self.origin_type.value}|{self.method}|{self.source_method}|{self.source}"
            )

        return f"{self.__class__.__name__}|{self.origin_type.value}|{self.method}|{self.source}"

    def __eq__(self, other):
        if isinstance(other, Origin):
            return (
                self.origin_type == other.origin_type
                and self.method == other.method
                and self.source_method == other.source_method
                and self.source == other.source
                and self.parameters_hash == other.parameters_hash
                and all(any(ooi == ooi2 for ooi2 in other.phantom_result or []) for ooi in self.phantom_result or [])
                and set(self.result) == set(other.result)
            )
        return False


class OriginParameter(BaseModel):
    origin_id: str
    reference: Reference

    @property
    def id(self) -> str:
        return f"{self.__class__.__name__}|{self.origin_id}|{self.reference}"
