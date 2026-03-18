from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel

from octopoes.models import DeclaredScanProfile
from octopoes.models.types import OOIType


class NormalizerObservation(BaseModel):
    type: Literal["observation"] = "observation"
    input_ooi: str
    results: list[OOIType]


class NormalizerDeclaration(BaseModel):
    type: Literal["declaration"] = "declaration"
    ooi: OOIType
    end_valid_time: datetime | None = None


class NormalizerAffirmation(BaseModel):
    type: Literal["affirmation"] = "affirmation"
    ooi: OOIType


class NormalizerResults(BaseModel):
    observations: list[NormalizerObservation] = []
    declarations: list[NormalizerDeclaration] = []
    affirmations: list[NormalizerAffirmation] = []
    scan_profiles: list[DeclaredScanProfile] = []


NormalizerOutput: TypeAlias = OOIType | NormalizerDeclaration | NormalizerAffirmation | DeclaredScanProfile
