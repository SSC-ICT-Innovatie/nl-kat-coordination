from bytes.database.db_models import BoefjeMetaInDB, NormalizerMetaInDB, RawFileInDB
from bytes.database.sql_meta_repository import (
    raw_meta_to_raw_file_in_db,
    to_boefje_meta,
    to_boefje_meta_in_db,
    to_mime_type,
    to_normalizer_meta,
    to_normalizer_meta_in_db,
    to_raw_data,
    to_raw_file_in_db,
)
from tests.loading import get_boefje_meta, get_normalizer_meta, get_raw_data


def test_context_mapping_boefje() -> None:
    boefje_meta = get_boefje_meta()
    boefje_meta_in_db = to_boefje_meta_in_db(boefje_meta)

    assert isinstance(boefje_meta_in_db, BoefjeMetaInDB)
    assert str(boefje_meta.id) == boefje_meta_in_db.id
    assert boefje_meta.boefje.id == boefje_meta_in_db.boefje_id
    assert boefje_meta.organization == boefje_meta_in_db.organization
    assert boefje_meta.input_ooi == boefje_meta_in_db.input_ooi
    assert boefje_meta.boefje.version == boefje_meta_in_db.boefje_version
    assert boefje_meta.started_at == boefje_meta_in_db.started_at
    assert boefje_meta.ended_at == boefje_meta_in_db.ended_at

    boefje_meta_new = to_boefje_meta(boefje_meta_in_db)

    assert boefje_meta == boefje_meta_new


def test_context_mapping_normalizer() -> None:
    normalizer_meta = get_normalizer_meta()
    normalizer_meta_in_db = to_normalizer_meta_in_db(normalizer_meta)

    # These will be hydrated by the ORM automatically
    normalizer_meta_in_db.raw_file = raw_meta_to_raw_file_in_db(normalizer_meta.raw_data, 1)
    normalizer_meta_in_db.raw_file.boefje_meta = to_boefje_meta_in_db(normalizer_meta.raw_data.boefje_meta)

    assert isinstance(normalizer_meta_in_db, NormalizerMetaInDB)
    assert str(normalizer_meta.id) == normalizer_meta_in_db.id
    assert normalizer_meta.normalizer.id == normalizer_meta_in_db.normalizer_id
    assert normalizer_meta.normalizer.version == normalizer_meta_in_db.normalizer_version
    assert normalizer_meta.started_at == normalizer_meta_in_db.started_at
    assert normalizer_meta.ended_at == normalizer_meta_in_db.ended_at
    assert str(normalizer_meta.raw_data.id) == normalizer_meta_in_db.raw_file_id

    normalizer_meta_new = to_normalizer_meta(normalizer_meta_in_db)

    assert normalizer_meta == normalizer_meta_new


def test_context_mapping_raw() -> None:
    raw_data = get_raw_data()
    raw_data_in_db = to_raw_file_in_db(raw_data, None)

    # These will be hydrated by the ORM automatically
    raw_data_in_db.boefje_meta = to_boefje_meta_in_db(raw_data.boefje_meta)

    assert isinstance(raw_data_in_db, RawFileInDB)
    assert raw_data.hash_retrieval_link == raw_data_in_db.hash_retrieval_link
    assert raw_data.secure_hash == raw_data_in_db.secure_hash
    assert raw_data.signing_provider_url is None
    assert raw_data.mime_types == {to_mime_type(mime_type) for mime_type in raw_data_in_db.mime_types}

    raw_data_new = to_raw_data(raw_data_in_db, raw_data.value)

    assert raw_data == raw_data_new
