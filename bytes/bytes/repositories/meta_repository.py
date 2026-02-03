from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Query

from bytes.database.db_models import BoefjeMetaInDB, NormalizerMetaInDB, RawFileInDB
from bytes.models import BoefjeMeta, MimeType, NormalizerMeta, RawData, RawDataMeta


class BoefjeMetaFilter(BaseModel):
    organization: str

    boefje_id: str | None = None
    input_ooi: str | None = "*"
    limit: int = 1
    offset: int = 0
    descending: bool = True


class NormalizerMetaFilter(BaseModel):
    organization: str | None = None
    normalizer_id: str | None = None
    raw_id: UUID | None = None
    limit: int = 1
    offset: int = 0
    descending: bool = True


class RawDataFilter(BaseModel):
    organization: list[str] | None = None
    boefje_meta_id: UUID | None = None
    raw_ids: list[UUID] | None = None
    normalized: bool | None = None
    mime_types: list[MimeType] = Field(default_factory=list)
    limit: int | None = 1
    offset: int | None = 0

    def apply(self, query: Query) -> Query:
        if self.boefje_meta_id:
            query = query.filter(RawFileInDB.boefje_meta_id == str(self.boefje_meta_id))

        if self.organization:
            if len(self.organization) == 1:
                query = query.join(BoefjeMetaInDB).filter(BoefjeMetaInDB.organization == self.organization[0])
            else:
                query = query.join(BoefjeMetaInDB).filter(BoefjeMetaInDB.organization.in_(self.organization))

        if self.normalized:
            query = query.join(NormalizerMetaInDB, isouter=False)

        if self.normalized is False:  # it can also be None, in which case we do not want a filter
            query = query.join(NormalizerMetaInDB, isouter=True).filter(NormalizerMetaInDB.id.is_(None))

        if self.mime_types:
            query = query.filter(RawFileInDB.mime_types.contains([m.value for m in self.mime_types]))

        if self.raw_ids:
            query = query.filter(RawFileInDB.id.in_([x.hex for x in self.raw_ids]))

        return query.offset(self.offset).limit(self.limit)


class MetaDataRepository:
    def __enter__(self) -> None:
        pass

    def __exit__(self, _exc_type: type[Exception], _exc_value: str, _exc_traceback: str) -> None:
        pass

    def save_boefje_meta(self, boefje_meta: BoefjeMeta) -> None:
        raise NotImplementedError()

    def get_boefje_meta_by_id(self, boefje_meta_id: UUID) -> BoefjeMeta:
        raise NotImplementedError()

    def get_boefje_meta(self, query_filter: BoefjeMetaFilter) -> list[BoefjeMeta]:
        raise NotImplementedError()

    def save_normalizer_meta(self, normalizer_meta: NormalizerMeta) -> None:
        raise NotImplementedError()

    def get_normalizer_meta_by_id(self, normalizer_meta_id: UUID) -> NormalizerMeta:
        raise NotImplementedError()

    def get_normalizer_meta(self, query_filter: NormalizerMetaFilter) -> list[NormalizerMeta]:
        raise NotImplementedError()

    def get_normalizer_metas(self, normalizer_metas: list[UUID]) -> dict[str, NormalizerMeta]:
        raise NotImplementedError()

    def save_raw(self, raw: RawData) -> UUID:
        raise NotImplementedError()

    def get_raw_by_id(self, raw_id: UUID) -> RawData:
        raise NotImplementedError()

    def get_raw(self, query_filter: RawDataFilter) -> list[RawDataMeta]:
        raise NotImplementedError()

    def get_raws(self, query_filter: RawDataFilter) -> list[tuple[UUID, RawData]]:
        raise NotImplementedError()

    def has_raw(self, boefje_meta: BoefjeMeta, mime_types: list[MimeType]) -> bool:
        raise NotImplementedError()

    def get_raw_file_count_per_organization(self) -> dict[str, int]:
        raise NotImplementedError()

    def get_raw_file_count_per_mime_type(self, query_filter: RawDataFilter) -> dict[str, int]:
        raise NotImplementedError()

    def get_raw_meta_by_id(self, raw_id: UUID) -> RawDataMeta:
        raise NotImplementedError()
