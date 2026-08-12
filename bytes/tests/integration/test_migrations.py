import alembic.config

from bytes.database.sql_meta_repository import SQLMetaDataRepository
from bytes.models import MimeType
from tests.loading import get_boefje_meta, get_raw_data


def test_clean_mime_types(meta_repository: SQLMetaDataRepository) -> None:
    alembic.config.main(argv=["--config", "/app/bytes/bytes/alembic.ini", "--raiseerr", "downgrade", "d216ad75177d"])

    with meta_repository:
        boefje_meta = get_boefje_meta()
        meta_repository.save_boefje_meta(boefje_meta)

        raw = get_raw_data()
        raw.mime_types.add(MimeType(value=raw.boefje_meta.boefje.id))
        raw_id_1 = meta_repository.save_raw(raw)

        raw.mime_types.add(
            MimeType(value=f"boefje/{raw.boefje_meta.boefje.id}-ce293f79fd3c809a300a2837bb1da4f7115fc034a1f78")
        )
        raw_id_2 = meta_repository.save_raw(raw)

        raw.mime_types.add(
            MimeType(value=f"boefje/{raw.boefje_meta.boefje.id}-ba293f79fd3c809a300a2837bb1da4f7115fc034a1f78")
        )
        raw_id_3 = meta_repository.save_raw(raw)

    assert len(meta_repository.get_raw_meta_by_id(raw_id_1).mime_types) == 3
    assert len(meta_repository.get_raw_meta_by_id(raw_id_2).mime_types) == 4
    assert len(meta_repository.get_raw_meta_by_id(raw_id_3).mime_types) == 5

    alembic.config.main(argv=["--config", "/app/bytes/bytes/alembic.ini", "--raiseerr", "upgrade", "head"])

    assert len(meta_repository.get_raw_meta_by_id(raw_id_1).mime_types) == 2
    assert len(meta_repository.get_raw_meta_by_id(raw_id_2).mime_types) == 2
    assert len(meta_repository.get_raw_meta_by_id(raw_id_3).mime_types) == 2

    assert meta_repository.get_raw_meta_by_id(raw_id_3).mime_types == get_raw_data().mime_types
