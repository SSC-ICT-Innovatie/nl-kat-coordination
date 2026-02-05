import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import DataError

from bytes.database.sql_meta_repository import SQLMetaDataRepository
from bytes.models import MimeType
from bytes.repositories.meta_repository import BoefjeMetaFilter, NormalizerMetaFilter, RawDataFilter
from tests.loading import get_boefje_meta, get_normalizer_meta, get_raw_data


def test_save_boefje_meta(meta_repository: SQLMetaDataRepository) -> None:
    boefje_meta = get_boefje_meta()
    second_boefje_meta = get_boefje_meta(uuid.uuid4(), boefje_id=boefje_meta.boefje.id, input_ooi=None)
    third_boefje_meta = get_boefje_meta(uuid.uuid4(), boefje_id="kat-test-2", input_ooi=boefje_meta.input_ooi)

    second_boefje_meta.started_at = boefje_meta.started_at + timedelta(hours=5)
    third_boefje_meta.started_at = boefje_meta.started_at - timedelta(hours=5)

    with meta_repository:
        meta_repository.save_boefje_meta(boefje_meta)
        meta_repository.save_boefje_meta(second_boefje_meta)
        meta_repository.save_boefje_meta(third_boefje_meta)

    boefje_meta_from_db = meta_repository.get_boefje_meta_by_id(boefje_meta.id)
    assert boefje_meta == boefje_meta_from_db

    first_and_second = meta_repository.get_boefje_meta(
        BoefjeMetaFilter(
            organization=boefje_meta.organization, boefje_id=boefje_meta.boefje.id, limit=3, descending=False
        )
    )
    assert len(first_and_second) == 2

    assert boefje_meta == first_and_second[0]
    assert second_boefje_meta == first_and_second[1]

    second_and_first = meta_repository.get_boefje_meta(
        BoefjeMetaFilter(organization=boefje_meta.organization, boefje_id=boefje_meta.boefje.id, limit=3)
    )
    assert len(second_and_first) == 2

    assert boefje_meta == second_and_first[1]
    assert second_boefje_meta == second_and_first[0]

    first_and_third = meta_repository.get_boefje_meta(
        BoefjeMetaFilter(organization=boefje_meta.organization, input_ooi=boefje_meta.input_ooi, limit=3)
    )
    assert len(first_and_third) == 2

    assert boefje_meta == first_and_third[0]
    assert third_boefje_meta == first_and_third[1]

    third = meta_repository.get_boefje_meta(
        BoefjeMetaFilter(organization=boefje_meta.organization, input_ooi=boefje_meta.input_ooi, descending=False)
    )
    assert third_boefje_meta == third[0]

    wrong_organization = meta_repository.get_boefje_meta(
        BoefjeMetaFilter(organization="test2", input_ooi=boefje_meta.input_ooi, descending=False)
    )
    assert wrong_organization == []


def test_data_error_is_raised_when_boefje_id_is_too_long(meta_repository: SQLMetaDataRepository) -> None:
    boefje_meta = get_boefje_meta()

    with meta_repository:
        boefje_meta.boefje.id = 64 * "a"
        meta_repository.save_boefje_meta(boefje_meta)

    with pytest.raises(DataError), meta_repository:
        boefje_meta.id = str(uuid.uuid4())
        boefje_meta.boefje.id = 65 * "a"
        meta_repository.save_boefje_meta(boefje_meta)

    meta_repository.session.rollback()  # make sure to roll back the session, so we can clean up the db


def test_data_error_is_raised_when_organization_id_is_too_long(meta_repository: SQLMetaDataRepository) -> None:
    boefje_meta = get_boefje_meta()

    with meta_repository:
        boefje_meta.organization = 32 * "t"
        meta_repository.save_boefje_meta(boefje_meta)

    with pytest.raises(DataError), meta_repository:
        boefje_meta.id = str(uuid.uuid4())
        boefje_meta.organization = 33 * "t"
        meta_repository.save_boefje_meta(boefje_meta)

    meta_repository.session.rollback()  # make sure to roll back the session, so we can clean up the db


def test_save_raw(meta_repository: SQLMetaDataRepository) -> None:
    raw = get_raw_data()

    with meta_repository:
        meta_repository.save_boefje_meta(raw.boefje_meta)

    raw.mime_types = [MimeType(value="text/plain")]

    with meta_repository:
        raw_id = meta_repository.save_raw(raw)
        meta_repository.save_raw(raw)

    query_filter = RawDataFilter(
        organization=[raw.boefje_meta.organization], boefje_meta_id=raw.boefje_meta.id, normalized=False
    )
    first_updated_raw = meta_repository.get_raw(query_filter).pop()

    assert first_updated_raw.signing_provider_url in ["https://test", "https://freetsa.org/tsr"]  # Depends on CI env
    assert "hash_retrieval_link" in first_updated_raw.json()
    assert "secure_hash" in first_updated_raw.json()
    assert "signing_provider" in first_updated_raw.json()

    query_filter = RawDataFilter(
        organization=[raw.boefje_meta.organization],
        boefje_meta_id=raw.boefje_meta.id,
        mime_types=[MimeType(value="text/plain")],
    )
    first_updated_raw = meta_repository.get_raw(query_filter).pop()
    assert "hash_retrieval_link" in first_updated_raw.json()
    assert "secure_hash" in first_updated_raw.json()
    assert "signing_provider" in first_updated_raw.json()

    query_filter = RawDataFilter(
        organization=[raw.boefje_meta.organization],
        boefje_meta_id=raw.boefje_meta.id,
        mime_types=[MimeType(value="bad/mime")],
    )
    empty_raws = meta_repository.get_raw(query_filter)
    assert empty_raws == []

    # No raw data has been normalized
    query_filter = RawDataFilter(organization=[raw.boefje_meta.organization], normalized=True)
    empty_raws = meta_repository.get_raw(query_filter)
    assert empty_raws == []

    with meta_repository:
        meta_repository.save_normalizer_meta(get_normalizer_meta(raw_id))

    # Now the raw data has been normalized
    non_empty_raws = meta_repository.get_raw(query_filter)
    assert len(non_empty_raws) == 1

    assert meta_repository.get_raw_file_count_per_organization() == {"test": 2}


def test_filter_raw_on_organization(meta_repository: SQLMetaDataRepository) -> None:
    raw = get_raw_data()
    raw2 = get_raw_data()
    raw2.boefje_meta.id = uuid.uuid4()

    with meta_repository:
        meta_repository.save_boefje_meta(raw.boefje_meta)
        meta_repository.save_raw(raw)
        meta_repository.save_boefje_meta(raw2.boefje_meta)
        meta_repository.save_raw(raw2)

    query_filter = RawDataFilter(
        organization=[raw.boefje_meta.organization], boefje_meta_id=raw.boefje_meta.id, normalized=False, limit=10
    )
    assert len(meta_repository.get_raw(query_filter)) == 1

    raw3 = get_raw_data()

    raw3.boefje_meta.organization = "test2"
    raw3.boefje_meta.id = uuid.uuid4()

    with meta_repository:
        meta_repository.save_boefje_meta(raw3.boefje_meta)
        meta_repository.save_raw(raw3)

    assert len(meta_repository.get_raw(query_filter)) == 1

    query_filter.organization = ["test2"]
    assert len(meta_repository.get_raw(query_filter)) == 0

    query_filter.boefje_meta_id = raw3.boefje_meta.id
    assert len(meta_repository.get_raw(query_filter)) == 1

    assert {x.boefje_meta for x in meta_repository.get_raw(RawDataFilter(organization=["test"], limit=10))} == {
        raw.boefje_meta,
        raw2.boefje_meta,
    }
    assert {x.boefje_meta for x in meta_repository.get_raw(RawDataFilter(limit=10))} == {
        raw.boefje_meta,
        raw2.boefje_meta,
        raw3.boefje_meta,
    }
    assert {
        x.boefje_meta for x in meta_repository.get_raw(RawDataFilter(organization=["test", "test2"], limit=10))
    } == {raw.boefje_meta, raw2.boefje_meta, raw3.boefje_meta}


def test_filter_raw_not_on_organization(meta_repository: SQLMetaDataRepository) -> None:
    raw = get_raw_data()
    raw2 = get_raw_data()
    raw2.boefje_meta.id = "c5d7d1da-7d94-4ac4-b0f6-ac065eeb0c97"

    with meta_repository:
        meta_repository.save_boefje_meta(raw.boefje_meta)
        meta_repository.save_raw(raw)
        meta_repository.save_raw(raw)
        meta_repository.save_raw(raw)
        meta_repository.save_raw(raw)
        meta_repository.save_raw(raw)
        meta_repository.save_boefje_meta(raw2.boefje_meta)
        meta_repository.save_raw(raw2)
        meta_repository.save_raw(raw2)

    # Test offset-limit
    assert len(meta_repository.get_raw(RawDataFilter(boefje_meta_id=raw.boefje_meta.id, limit=2))) == 2
    assert len(meta_repository.get_raw(RawDataFilter(boefje_meta_id=raw.boefje_meta.id, limit=6))) == 5
    assert len(meta_repository.get_raw(RawDataFilter(boefje_meta_id=raw.boefje_meta.id, limit=2, offset=1))) == 2
    assert len(meta_repository.get_raw(RawDataFilter(boefje_meta_id=raw.boefje_meta.id, limit=2, offset=4))) == 1

    # Test without boefje_meta id
    assert len(meta_repository.get_raw(RawDataFilter(limit=2, offset=4))) == 2
    assert len(meta_repository.get_raw(RawDataFilter(limit=100))) == 7
    assert len(meta_repository.get_raw(RawDataFilter(limit=100, normalized=False))) == 7


def test_filter_normalizer_meta(meta_repository: SQLMetaDataRepository) -> None:
    with meta_repository:
        boefje_meta = get_boefje_meta()
        meta_repository.save_boefje_meta(boefje_meta)

        raw_id = meta_repository.save_raw(get_raw_data())

        normalizer_meta = get_normalizer_meta(raw_id)
        meta_repository.save_normalizer_meta(normalizer_meta)

        raw_id = meta_repository.save_raw(get_raw_data())

        normalizer_meta = get_normalizer_meta(raw_id)
        normalizer_meta.id = str(uuid.uuid4())
        meta_repository.save_normalizer_meta(normalizer_meta)

        boefje_meta = get_boefje_meta()
        boefje_meta.id = str(uuid.uuid4())
        boefje_meta.organization = "test2"
        meta_repository.save_boefje_meta(boefje_meta)

        raw = get_raw_data()
        raw.boefje_meta = boefje_meta
        raw_id = meta_repository.save_raw(raw)

        normalizer_meta = get_normalizer_meta(raw_id)
        normalizer_meta.id = str(uuid.uuid4())
        meta_repository.save_normalizer_meta(normalizer_meta)

    normalizer_metas = meta_repository.get_normalizer_meta(
        NormalizerMetaFilter(raw_id=raw_id, normalizer_id="kat_test.main", limit=10)
    )
    assert len(normalizer_metas) == 1

    normalizer_metas = meta_repository.get_normalizer_meta(
        NormalizerMetaFilter(organization="test", normalizer_id="kat_test.main", limit=10)
    )
    assert len(normalizer_metas) == 2
   
    normalizer_metas = meta_repository.get_normalizer_meta(
        NormalizerMetaFilter(organization="test", normalizer_id="kat_main", limit=10)
    )
    assert len(normalizer_metas) == 0

    normalizer_metas = meta_repository.get_normalizer_meta(NormalizerMetaFilter(organization="test", limit=10))
    assert len(normalizer_metas) == 2

    meta_ids = [meta.id for meta in normaliser_metas]
    normalizer_metas = meta_repository.get_normalizer_metas(meta_ids)
    assert len(normalizer_metas) == 2
    
    normalizer_metas = meta_repository.get_normalizer_meta(NormalizerMetaFilter(organization="test2", limit=10))
    assert len(normalizer_metas) == 1

    normalizer_metas = meta_repository.get_normalizer_meta(NormalizerMetaFilter(organization="test3", limit=10))
    assert len(normalizer_metas) == 0


def test_save_normalizer_meta(meta_repository: SQLMetaDataRepository) -> None:
    with meta_repository:
        boefje_meta = get_boefje_meta()
        meta_repository.save_boefje_meta(boefje_meta)

        raw_id = meta_repository.save_raw(get_raw_data())
        normalizer_meta = get_normalizer_meta(raw_id)

        meta_repository.save_normalizer_meta(normalizer_meta)

    normalizer_meta_from_db = meta_repository.get_normalizer_meta_by_id(normalizer_meta.id)
    boefje_meta_from_db = meta_repository.get_boefje_meta_by_id(normalizer_meta.raw_data.boefje_meta.id)

    assert boefje_meta_from_db == normalizer_meta.raw_data.boefje_meta

    normalizer_meta.raw_data.secure_hash = normalizer_meta_from_db.raw_data.secure_hash
    normalizer_meta.raw_data.hash_retrieval_link = normalizer_meta_from_db.raw_data.hash_retrieval_link
    normalizer_meta.raw_data.signing_provider_url = normalizer_meta_from_db.raw_data.signing_provider_url

    assert normalizer_meta == normalizer_meta_from_db


def test_normalizer_id_length(meta_repository: SQLMetaDataRepository) -> None:
    with meta_repository:
        boefje_meta = get_boefje_meta()
        meta_repository.save_boefje_meta(boefje_meta)

        raw_id = meta_repository.save_raw(get_raw_data())
        normalizer_meta = get_normalizer_meta(raw_id)

        normalizer_meta.id = str(uuid.uuid4())
        normalizer_meta.normalizer.id = 64 * "a"
        meta_repository.save_normalizer_meta(normalizer_meta)

    with pytest.raises(DataError), meta_repository:
        normalizer_meta.id = str(uuid.uuid4())
        normalizer_meta.normalizer.id = 65 * "a"
        meta_repository.save_normalizer_meta(normalizer_meta)

    meta_repository.session.rollback()  # make sure to roll back the session, so we can clean up the db


def test_normalizer_meta_pointing_to_raw_id(meta_repository: SQLMetaDataRepository) -> None:
    with meta_repository:
        boefje_meta = get_boefje_meta()
        meta_repository.save_boefje_meta(boefje_meta)

        raw_id = meta_repository.save_raw(get_raw_data())
        normalizer_meta = get_normalizer_meta(raw_id)

        meta_repository.save_normalizer_meta(normalizer_meta)

    normalizer_meta_from_db = meta_repository.get_normalizer_meta_by_id(normalizer_meta.id)
    boefje_meta_from_db = meta_repository.get_boefje_meta_by_id(normalizer_meta.raw_data.boefje_meta.id)

    assert boefje_meta_from_db == normalizer_meta.raw_data.boefje_meta

    normalizer_meta.raw_data.secure_hash = normalizer_meta_from_db.raw_data.secure_hash
    normalizer_meta.raw_data.hash_retrieval_link = normalizer_meta_from_db.raw_data.hash_retrieval_link
    normalizer_meta.raw_data.signing_provider_url = normalizer_meta_from_db.raw_data.signing_provider_url

    assert normalizer_meta == normalizer_meta_from_db
