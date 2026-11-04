import uuid

from pydantic import BaseModel

from .boefje import BoefjeMeta


class RawData(BaseModel):
    id: uuid.UUID
    boefje_meta: BoefjeMeta
    mime_types: list[dict[str, str]]
    name: str | None = None
    secure_hash: str | None = None
    hash_retrieval_link: str | None = None
