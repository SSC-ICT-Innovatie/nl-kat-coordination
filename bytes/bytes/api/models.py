from enum import StrEnum

from pydantic import BaseModel, Field


class RawResponse(BaseModel):
    status: str
    message: str
    ids: list[str] | None = None


class File(BaseModel):
    name: str
    content: str = Field(json_schema_extra={"contentEncoding": "base64"})
    tags: list[str] = Field(default_factory=list)


class StatusEnum(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class BoefjeOutput(BaseModel):
    status: StatusEnum = StatusEnum.COMPLETED
    files: list[File] = Field(default_factory=list)
