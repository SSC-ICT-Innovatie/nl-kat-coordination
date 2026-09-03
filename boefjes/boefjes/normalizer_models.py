from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

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


class NormalizerRawFile(BaseModel):
    """A raw file produced by a normalizer (e.g. an unpacker/decompressor extracting a compound file
    such as a HAR or archive). The file is stored back in Bytes and re-dispatched to downstream
    normalizers by its mime types. `mime_types` should include at least one discriminating tag so the
    set is unique per boefje_meta (Bytes deduplicates raws on their mime-type set)."""

    type: Literal["raw_file"] = "raw_file"
    content: bytes
    mime_types: set[str] = Field(default_factory=set)


class NormalizerResults(BaseModel):
    observations: list[NormalizerObservation] = []
    declarations: list[NormalizerDeclaration] = []
    affirmations: list[NormalizerAffirmation] = []
    scan_profiles: list[DeclaredScanProfile] = []
    raw_files: list[NormalizerRawFile] = []


NormalizerOutput: TypeAlias = (
    OOIType | NormalizerDeclaration | NormalizerAffirmation | DeclaredScanProfile | NormalizerRawFile
)
