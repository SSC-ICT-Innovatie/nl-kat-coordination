from uuid import UUID

from bytes.models import BoefjeMeta, RawData


class BytesFileNotFoundException(FileNotFoundError):
    """Exception for when no requested Bytes file was found."""


class RawRepository:
    def save_raw(self, raw_id: UUID, raw: RawData) -> None:
        raise NotImplementedError()

    def get_raw(self, raw_id: UUID, boefje_meta: BoefjeMeta) -> RawData:
        raise NotImplementedError()

    def get_raws(self, raw_metas_pairs: list[tuple[UUID, BoefjeMeta]]) -> list[tuple[UUID, RawData]]:
        raise NotImplementedError()
