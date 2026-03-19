import uuid
from base64 import b64decode, b64encode

import httpx
import pytest
from httpx import HTTPError
from prometheus_client.parser import text_string_to_metric_families

from bytes.api.models import BoefjeOutput, File, StatusEnum
from bytes.models import MimeType
from bytes.rabbitmq import RabbitMQEventManager
from bytes.repositories.meta_repository import BoefjeMetaFilter, NormalizerMetaFilter, RawDataFilter
from tests.client import BytesAPIClient
from tests.loading import get_boefje_meta, get_normalizer_meta, get_raw_data


def test_login(bytes_api_client: BytesAPIClient) -> None:
    bytes_api_client.login()
    assert "Authorization" in bytes_api_client.client.headers
    assert "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" in bytes_api_client.client.headers["Authorization"]


def test_metrics(bytes_api_client: BytesAPIClient) -> None:
    metrics = bytes_api_client.get_metrics()

    metrics = list(text_string_to_metric_families(metrics.decode()))
    assert len(metrics) == 2
    assert metrics[0].name == "bytes_database_organizations_total"
    assert len(metrics[0].samples) == 1
    assert metrics[1].name == "bytes_database_raw_files_total"
    assert len(metrics[1].samples) == 0

    database_organizations, database_files = metrics

    assert database_organizations.samples[0].value == 0.0

    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)
    bytes_api_client.save_raw(boefje_meta.id, b"test 123")
    bytes_api_client.save_raw(boefje_meta.id, b"test 12334", ["text/boefje"])

    metrics = bytes_api_client.get_metrics()
    metrics = list(text_string_to_metric_families(metrics.decode()))
    assert len(metrics[0].samples) == 1
    assert len(metrics[1].samples) == 1
    database_organizations, database_files = metrics

    assert database_organizations.samples[0].value == 1.0

    assert database_files.samples[0].labels["organization_id"] == "test"
    assert database_files.samples[0].value == 2.0

    boefje_meta = get_boefje_meta()
    boefje_meta.id = str(uuid.uuid4())
    boefje_meta.organization = "test2"
    bytes_api_client.save_boefje_meta(boefje_meta)
    bytes_api_client.save_raw(boefje_meta.id, b"test 123")

    metrics = bytes_api_client.get_metrics()
    metrics = list(text_string_to_metric_families(metrics.decode()))
    assert len(metrics[0].samples) == 1
    assert len(metrics[1].samples) == 2
    database_organizations, database_files = metrics

    assert database_organizations.samples[0].value == 2.0

    assert len(database_files.samples) == 2
    assert database_files.samples[0].labels["organization_id"] == "test"
    assert database_files.samples[0].value == 2.0
    assert database_files.samples[1].labels["organization_id"] == "test2"
    assert database_files.samples[1].value == 1.0


def test_get_mime_type_count(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    bytes_api_client.save_raw(boefje_meta.id, b"test 123", ["boefje"])
    raw_id = bytes_api_client.save_raw(boefje_meta.id, b"test 12334", ["text/boefje", "boefje"])

    normalizer_meta = get_normalizer_meta(raw_id)
    bytes_api_client.save_normalizer_meta(normalizer_meta)

    assert bytes_api_client.get_mime_type_count(RawDataFilter(organization=["test"])) == {"boefje": 2, "text/boefje": 1}

    assert bytes_api_client.get_mime_type_count(RawDataFilter(organization=["test"], normalized=True)) == {
        "boefje": 1,
        "text/boefje": 1,
    }
    assert bytes_api_client.get_mime_type_count(RawDataFilter(organization=["test"], normalized=False)) == {"boefje": 1}


def test_boefje_meta(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)
    retrieved_boefje_meta = bytes_api_client.get_boefje_meta_by_id(boefje_meta.id)

    assert boefje_meta == retrieved_boefje_meta

    with pytest.raises(HTTPError) as ctx:
        bytes_api_client.save_boefje_meta(boefje_meta)

    assert ctx._excinfo[1].response.json() == {
        "status": "failed",
        "message": "Integrity error: object might already exist",
    }


def test_filtered_boefje_meta(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    query_filter = BoefjeMetaFilter(organization=boefje_meta.organization, boefje_id=boefje_meta.boefje.id)
    retrieved_boefje_metas = bytes_api_client.get_boefje_meta(query_filter)

    assert len(retrieved_boefje_metas) == 1
    assert boefje_meta == retrieved_boefje_metas[0]

    second_boefje_meta = get_boefje_meta(uuid.uuid4(), input_ooi="Network|internet")
    bytes_api_client.save_boefje_meta(second_boefje_meta)

    query_filter = BoefjeMetaFilter(organization=boefje_meta.organization, boefje_id=boefje_meta.boefje.id, limit=2)
    retrieved_boefje_metas = bytes_api_client.get_boefje_meta(query_filter)
    assert len(retrieved_boefje_metas) == 2
    assert boefje_meta == retrieved_boefje_metas[0]
    assert second_boefje_meta == retrieved_boefje_metas[1]

    query_filter = BoefjeMetaFilter(organization=boefje_meta.organization, input_ooi="Network|internet", limit=2)
    retrieved_boefje_metas = bytes_api_client.get_boefje_meta(query_filter)
    assert len(retrieved_boefje_metas) == 1
    assert second_boefje_meta == retrieved_boefje_metas[0]


def test_normalizer_meta(bytes_api_client: BytesAPIClient, event_manager: RabbitMQEventManager) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    raw = get_raw_data()
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw.value, [m.value for m in raw.mime_types])
    normalizer_meta = get_normalizer_meta(raw_id)

    bytes_api_client.save_normalizer_meta(normalizer_meta)
    retrieved_normalizer_meta = bytes_api_client.get_normalizer_meta_by_id(normalizer_meta.id)

    normalizer_meta.raw_data.secure_hash = retrieved_normalizer_meta.raw_data.secure_hash
    normalizer_meta.raw_data.hash_retrieval_link = retrieved_normalizer_meta.raw_data.hash_retrieval_link
    normalizer_meta.raw_data.signing_provider_url = retrieved_normalizer_meta.raw_data.signing_provider_url

    normalizer_meta.raw_data.mime_types = sorted(normalizer_meta.raw_data.mime_types)
    retrieved_normalizer_meta.raw_data.mime_types = sorted(retrieved_normalizer_meta.raw_data.mime_types)

    assert normalizer_meta.model_dump_json() == retrieved_normalizer_meta.model_dump_json()


def test_filtered_normalizer_meta(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    raw = get_raw_data()
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw.value, [m.value for m in raw.mime_types])
    normalizer_meta = get_normalizer_meta(raw_id)

    bytes_api_client.save_normalizer_meta(normalizer_meta)

    query_filter = NormalizerMetaFilter(
        organization=boefje_meta.organization, normalizer_id=normalizer_meta.normalizer.id, limit=10
    )
    retrieved_normalizer_metas = bytes_api_client.get_normalizer_meta(query_filter)
    assert len(retrieved_normalizer_metas) == 1

    normalizer_meta.raw_data.secure_hash = retrieved_normalizer_metas[0].raw_data.secure_hash
    normalizer_meta.raw_data.hash_retrieval_link = retrieved_normalizer_metas[0].raw_data.hash_retrieval_link
    normalizer_meta.raw_data.signing_provider_url = retrieved_normalizer_metas[0].raw_data.signing_provider_url

    assert normalizer_meta == retrieved_normalizer_metas[0]

    second_normalizer_meta = get_normalizer_meta(raw_id)
    second_normalizer_meta.id = uuid.uuid4()
    bytes_api_client.save_normalizer_meta(second_normalizer_meta)

    third_normalizer_meta = get_normalizer_meta(raw_id)
    third_normalizer_meta.id = uuid.uuid4()
    third_normalizer_meta.normalizer.id = "third/normalizer"
    bytes_api_client.save_normalizer_meta(third_normalizer_meta)

    retrieved_normalizer_metas = bytes_api_client.get_normalizer_meta(query_filter)
    assert len(retrieved_normalizer_metas) == 2
    assert normalizer_meta == retrieved_normalizer_metas[0]

    query_filter.offset = 1
    retrieved_normalizer_metas = bytes_api_client.get_normalizer_meta(query_filter)
    assert len(retrieved_normalizer_metas) == 1

    second_normalizer_meta.raw_data.secure_hash = retrieved_normalizer_metas[0].raw_data.secure_hash
    second_normalizer_meta.raw_data.hash_retrieval_link = retrieved_normalizer_metas[0].raw_data.hash_retrieval_link
    second_normalizer_meta.raw_data.signing_provider_url = retrieved_normalizer_metas[0].raw_data.signing_provider_url

    assert second_normalizer_meta == retrieved_normalizer_metas[0]


def test_normalizer_meta_pointing_to_raw_id(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    raw = get_raw_data()
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw.value, [m.value for m in raw.mime_types])
    normalizer_meta = get_normalizer_meta(raw_id)

    bytes_api_client.save_normalizer_meta(normalizer_meta)
    retrieved_normalizer_meta = bytes_api_client.get_normalizer_meta_by_id(normalizer_meta.id)

    normalizer_meta.raw_data.secure_hash = retrieved_normalizer_meta.raw_data.secure_hash
    normalizer_meta.raw_data.hash_retrieval_link = retrieved_normalizer_meta.raw_data.hash_retrieval_link
    normalizer_meta.raw_data.signing_provider_url = retrieved_normalizer_meta.raw_data.signing_provider_url

    assert normalizer_meta == retrieved_normalizer_meta


def test_raw(bytes_api_client: BytesAPIClient, event_manager: RabbitMQEventManager) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    raw = b"test 123"
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw)

    retrieved_raw = bytes_api_client.get_raw(raw_id)

    assert retrieved_raw == raw

    method, properties, body = event_manager.connection.channel().basic_get("raw_file_received")
    event_manager.connection.channel().basic_ack(method.delivery_tag)

    assert str(boefje_meta.id) in body.decode()


def test_raw_big(bytes_api_client: BytesAPIClient, event_manager: RabbitMQEventManager) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    raw = b"test 123" * 100000
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw)

    retrieved_raw = bytes_api_client.get_raw(raw_id)

    assert retrieved_raw == raw

    method, properties, body = event_manager.connection.channel().basic_get("raw_file_received")
    event_manager.connection.channel().basic_ack(method.delivery_tag)

    assert str(boefje_meta.id) in body.decode()


def test_save_raw_with_one_mime_type(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta(meta_id=uuid.uuid4())
    bytes_api_client.save_boefje_meta(boefje_meta)
    mime_type = "text/kat-test"

    raw = b"test 123456"
    raw_id = bytes_api_client.save_raw(boefje_meta.id, raw, [mime_type])
    retrieved_raw = bytes_api_client.get_raw(raw_id)

    assert retrieved_raw == raw
    assert (
        len(
            bytes_api_client.get_raw_metas(
                RawDataFilter(boefje_meta_id=boefje_meta.id, normalized=False, mime_types=[MimeType(value="bad/mime")])
            )
        )
        == 0
    )


def test_save_raw_no_mime_types(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta(meta_id=uuid.uuid4())
    bytes_api_client.save_boefje_meta(boefje_meta)

    bytes_api_client.login()

    raw_url = f"{bytes_api_client.client.base_url}/bytes/raw"

    raw = b"second test 123456"
    file_name = "raw"
    response = httpx.post(
        raw_url,
        json={"files": [{"name": file_name, "content": b64encode(raw).decode(), "tags": []}]},
        headers=bytes_api_client.client.headers,
        params={"boefje_meta_id": str(boefje_meta.id)},
    )
    assert response.status_code == 200

    get_raw_without_mime_type_response = httpx.get(
        f"{raw_url}/{response.json()[file_name]}", headers=bytes_api_client.client.headers, timeout=30
    )

    assert get_raw_without_mime_type_response.status_code == 200
    assert get_raw_without_mime_type_response.content == raw


def test_get_many_actual_raw_files(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta(meta_id=uuid.uuid4())
    boefje_meta3 = get_boefje_meta(meta_id=uuid.uuid4())
    boefje_meta3.organization = "test2"

    bytes_api_client.save_boefje_meta(boefje_meta)
    bytes_api_client.save_boefje_meta(boefje_meta3)

    mime_types = ["text/kat-test", "text/html"]
    second_mime_types = ["text/kat-test", "text/status-code"]
    third_mime_types = ["text/kat-test", "text/test"]

    raw = b"test 123456"
    second_raw = b"second test 200"
    third_raw = b"third test 200"
    first_id = bytes_api_client.save_raw(boefje_meta.id, raw, mime_types)
    second_id = bytes_api_client.save_raw(boefje_meta.id, second_raw, second_mime_types)
    bytes_api_client.save_raw(boefje_meta3.id, third_raw, third_mime_types)

    result = bytes_api_client.get_raws(RawDataFilter(raw_ids=[first_id], limit=10))
    assert len(result) == 1
    assert b64decode(result[0]["content"]) == raw

    result = bytes_api_client.get_raws(RawDataFilter(raw_ids=[first_id, second_id], limit=10))
    assert len(result) == 2
    assert b64decode(result[0]["content"]) == raw
    assert b64decode(result[1]["content"]) == second_raw

    result = bytes_api_client.get_raws(RawDataFilter(organization=["test"], limit=10))
    assert len(result) == 2
    assert b64decode(result[0]["content"]) == raw
    assert b64decode(result[1]["content"]) == second_raw

    result = bytes_api_client.get_raws(RawDataFilter(organization=["test2"], limit=10))
    assert len(result) == 1
    assert b64decode(result[0]["content"]) == third_raw

    result = bytes_api_client.get_raws(RawDataFilter(organization=["test", "test2"], limit=10))
    assert len(result) == 3
    assert b64decode(result[0]["content"]) == raw
    assert b64decode(result[1]["content"]) == second_raw
    assert b64decode(result[2]["content"]) == third_raw


def test_raw_mimes(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta(meta_id=uuid.uuid4())
    bytes_api_client.save_boefje_meta(boefje_meta)
    mime_types = ["text/kat-test", "text/html"]
    second_mime_types = ["text/kat-test", "text/status-code"]

    raw = b"test 123456"
    second_raw = b"second test 200"
    first_id = bytes_api_client.save_raw(boefje_meta.id, raw, mime_types)
    second_id = bytes_api_client.save_raw(boefje_meta.id, second_raw, second_mime_types)

    first_meta = bytes_api_client.get_raw_meta(first_id)
    second_meta = bytes_api_client.get_raw_meta(second_id)

    assert first_meta.id != second_meta.id
    assert {x.value for x in first_meta.mime_types} == set(mime_types)
    assert {x.value for x in second_meta.mime_types} == set(second_mime_types)

    assert bytes_api_client.get_raw(first_id) == raw
    assert bytes_api_client.get_raw(second_id) == second_raw

    retrieved_raws = bytes_api_client.get_raw_metas(
        RawDataFilter(
            boefje_meta_id=boefje_meta.id, normalized=False, mime_types=[MimeType(value=x) for x in mime_types]
        )
    )
    assert len(retrieved_raws) == 1
    assert {x["value"] for x in retrieved_raws[0]["mime_types"]} == set(mime_types)

    retrieved_raws = bytes_api_client.get_raw_metas(
        RawDataFilter(boefje_meta_id=boefje_meta.id, normalized=False, mime_types=[MimeType(value="text/html")])
    )
    assert len(retrieved_raws) == 1
    assert {x["value"] for x in retrieved_raws[0]["mime_types"]} == set(mime_types)

    retrieved_raws = bytes_api_client.get_raw_metas(
        RawDataFilter(boefje_meta_id=boefje_meta.id, normalized=False, mime_types=[MimeType(value="bad/mime")])
    )
    assert len(retrieved_raws) == 0

    query_filter = RawDataFilter(
        organization=[boefje_meta.organization],
        boefje_meta_id=boefje_meta.id,
        mime_types=[MimeType(value="text/kat-test")],
        limit=3,
    )
    retrieved_raws = bytes_api_client.get_raw_metas(query_filter)

    assert len(retrieved_raws) == 2
    assert (
        retrieved_raws[0]["secure_hash"] == "sha512:ce89137e70b5f8433e787293f0c01332c0ca405d355a7080a50630340f7"
        "7bf5227561a01cba83272273513097d91f3bf9a8e8f17416fadfc1575028157cef2df"
    )
    assert (
        retrieved_raws[1]["secure_hash"] == "sha512:0ae68528b2daf4d9fd494ee378b043be8646489dbe1e7d63bbf33560f58"
        "d6c9b5abaa05387644c635f0c8a327a261e1435ad78de0cb30745d8bb05d76ddda612"
    )


def test_cannot_overwrite_raw(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    right_raw = b"test 123"
    first_raw_id = bytes_api_client.save_raw(boefje_meta.id, right_raw)
    bytes_api_client.save_raw(boefje_meta.id, b"321 test")

    retrieved_raw = bytes_api_client.get_raw(first_raw_id)

    assert retrieved_raw == right_raw


def test_save_multiple_raw_files(bytes_api_client: BytesAPIClient) -> None:
    boefje_meta = get_boefje_meta()
    bytes_api_client.save_boefje_meta(boefje_meta)

    first_raw = b"first"
    second_raw = b"second"
    boefje_output = BoefjeOutput(
        status=StatusEnum.COMPLETED,
        files=[
            File(name="first", content=b64encode(first_raw).decode(), tags=[]),
            File(name="second", content=b64encode(second_raw).decode(), tags=["mime", "type"]),
        ],
    )

    ids = bytes_api_client.save_raws(boefje_meta.id, boefje_output)

    assert bytes_api_client.get_raw(ids["first"]) == first_raw
    assert bytes_api_client.get_raw(ids["second"]) == second_raw

    assert bytes_api_client.get_raw_meta(ids["first"]).mime_types == set()
    assert {x.value for x in bytes_api_client.get_raw_meta(ids["second"]).mime_types} == {"mime", "type"}
