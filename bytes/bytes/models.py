from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, NewType
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field
from pydantic.v1.datetime_parse import parse_datetime

RetrievalLink = NewType("RetrievalLink", str)
SecureHash = NewType("SecureHash", str)


class EncryptionMiddleware(str, Enum):
    IDENTITY = "IDENTITY"
    NACL_SEALBOX = "NACL_SEALBOX"


class HashingAlgorithm(str, Enum):
    SHA512 = "sha512"
    SHA224 = "sha224"


class HashingRepositoryReference(str, Enum):
    IN_MEMORY = "IN_MEMORY"
    PASTEBIN = "PASTEBIN"
    RFC3161 = "RFC3161"


def _validate_timezone_aware_datetime(value: datetime) -> datetime:
    parsed = parse_datetime(value)
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ValueError(f"{parsed} is not timezone aware")
    return parsed


class MimeType(BaseModel):
    value: str

    def __hash__(self) -> int:
        return hash(self.value)

    def __lt__(self, other: MimeType) -> bool:
        return self.value < other.value


class Job(BaseModel):
    id: UUID
    started_at: AwareDatetime
    ended_at: AwareDatetime

    def __hash__(self) -> int:
        return self.id.int


class Boefje(BaseModel):
    id: str
    version: str | None = None


class Normalizer(BaseModel):
    id: str
    version: str | None = None


class BoefjeMeta(Job):
    boefje: Boefje
    input_ooi: str | None = None
    arguments: dict[str, Any]
    organization: str
    runnable_hash: str | None = None
    environment: dict[str, str] | None = None


class RawDataMeta(BaseModel):
    """Represents only the metadata of a RawData object, without its raw value. Used as an API response model."""

    id: UUID
    boefje_meta: BoefjeMeta
    mime_types: set[MimeType] = Field(default_factory=set)

    # These are set once the raw is saved
    secure_hash: SecureHash | None = None
    signing_provider_url: str | None = None
    hash_retrieval_link: RetrievalLink | None = None


class RawData(BaseModel):
    value: bytes
    boefje_meta: BoefjeMeta
    mime_types: set[MimeType] = Field(default_factory=set)

    # These are set once the raw is saved
    secure_hash: SecureHash | None = None
    signing_provider_url: str | None = None
    hash_retrieval_link: RetrievalLink | None = None


class NormalizerMeta(Job):
    raw_data: RawDataMeta
    normalizer: Normalizer
