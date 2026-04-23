import typing
from base64 import b64encode
from collections.abc import Callable
from functools import wraps
from typing import Any
from uuid import UUID

import httpx
from httpx import HTTPError, HTTPStatusError

from bytes.api.models import BoefjeOutput, File
from bytes.models import BoefjeMeta, NormalizerMeta, RawDataMeta
from bytes.repositories.meta_repository import BoefjeMetaFilter, NormalizerMetaFilter, RawDataFilter

BYTES_API_CLIENT_VERSION = "0.2"

ClientSessionMethod = Callable[..., Any]


def retry_with_login(function: ClientSessionMethod) -> ClientSessionMethod:
    @wraps(function)
    def wrapper(self, *args, **kwargs):  # type: ignore
        try:
            return function(self, *args, **kwargs)
        except HTTPError as error:
            if not isinstance(error, HTTPStatusError) or error.response.status_code != 401:
                raise

            self.login()
            return function(self, *args, **kwargs)

    return typing.cast(ClientSessionMethod, wrapper)


class BytesAPIClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.client = httpx.Client(
            base_url=base_url, headers={"User-Agent": f"bytes-api-client/{BYTES_API_CLIENT_VERSION}"}
        )
        self._credentials = {"username": username, "password": password}

    def login(self) -> None:
        self.client.headers.update(self._get_authentication_headers())

    @staticmethod
    def _verify_response(response: httpx.Response) -> None:
        response.raise_for_status()

    def _get_authentication_headers(self) -> dict[str, str]:
        return {"Authorization": f"bearer {self._get_token()}"}

    def _get_token(self) -> str:
        response = self.client.post(
            "/token", data=self._credentials, headers={"content-type": "application/x-www-form-urlencoded"}
        )

        return str(response.json()["access_token"])

    @retry_with_login
    def get_metrics(self) -> bytes:
        response = self.client.get("/metrics")

        self._verify_response(response)

        return response.content

    @retry_with_login
    def get_mime_type_count(self, query_filter: RawDataFilter) -> dict[str, str]:
        params = query_filter.model_dump(exclude_none=True)
        params["mime_types"] = [m.value for m in query_filter.mime_types]

        response = self.client.get("/bytes/mime_types", params=params)
        self._verify_response(response)

        return response.json()  # type: ignore

    @retry_with_login
    def save_boefje_meta(self, boefje_meta: BoefjeMeta) -> None:
        response = self.client.post("/bytes/boefje_meta", json=boefje_meta.model_dump(mode="json"))

        self._verify_response(response)

    @retry_with_login
    def get_boefje_meta_by_id(self, boefje_meta_id: UUID) -> BoefjeMeta:
        response = self.client.get(f"/bytes/boefje_meta/{boefje_meta_id}")
        self._verify_response(response)

        boefje_meta_json = response.json()
        return BoefjeMeta.model_validate(boefje_meta_json)

    @retry_with_login
    def get_boefje_meta(self, query_filter: BoefjeMetaFilter) -> list[BoefjeMeta]:
        response = self.client.get("/bytes/boefje_meta", params=query_filter.model_dump(exclude_none=True))
        self._verify_response(response)

        boefje_meta_json = response.json()
        return [BoefjeMeta.model_validate(boefje_meta) for boefje_meta in boefje_meta_json]

    @retry_with_login
    def save_normalizer_meta(self, normalizer_meta: NormalizerMeta) -> None:
        response = self.client.post("/bytes/normalizer_meta", json=normalizer_meta.model_dump(mode="json"))

        self._verify_response(response)

    @retry_with_login
    def get_normalizer_meta_by_id(self, normalizer_meta_id: UUID) -> NormalizerMeta:
        response = self.client.get(f"/bytes/normalizer_meta/{normalizer_meta_id}")
        self._verify_response(response)

        normalizer_meta_json = response.json()
        return NormalizerMeta.model_validate(normalizer_meta_json)

    @retry_with_login
    def get_normalizer_meta(self, query_filter: NormalizerMetaFilter) -> list[NormalizerMeta]:
        response = self.client.get("/bytes/normalizer_meta", params=query_filter.model_dump(exclude_none=True))
        self._verify_response(response)

        normalizer_meta_json = response.json()
        return [NormalizerMeta.model_validate(normalizer_meta) for normalizer_meta in normalizer_meta_json]

    @retry_with_login
    def save_raw(self, boefje_meta_id: UUID, raw: bytes, mime_types: list[str] | None = None) -> str:
        if not mime_types:
            mime_types = []

        file_name = "raw"  # The name provides a key for all ids returned, so this is arbitrary as we only upload 1 file
        response = self.client.post(
            "/bytes/raw",
            json={"files": [{"name": file_name, "content": b64encode(raw).decode(), "tags": mime_types}]},
            params={"boefje_meta_id": str(boefje_meta_id)},
        )
        self._verify_response(response)

        return response.json()[file_name]

    @retry_with_login
    def save_raws(self, boefje_meta_id: UUID, boefje_output: BoefjeOutput) -> dict[str, str]:
        response = self.client.post(
            "/bytes/raw", json=boefje_output.model_dump(mode="json"), params={"boefje_meta_id": str(boefje_meta_id)}
        )
        self._verify_response(response)

        return response.json()

    @retry_with_login
    def get_raw(self, raw_id: UUID) -> bytes:
        response = self.client.get(f"/bytes/raw/{raw_id}")
        self._verify_response(response)

        return response.content

    @retry_with_login
    def get_raw_meta(self, raw_id: UUID) -> RawDataMeta:
        response = self.client.get(f"/bytes/raw/{raw_id}/meta")
        self._verify_response(response)

        return RawDataMeta.model_validate(response.json())

    @retry_with_login
    def get_raw_metas(self, query_filter: RawDataFilter) -> dict[str, str]:
        params = query_filter.model_dump(exclude_none=True)
        params["mime_types"] = [m.value for m in query_filter.mime_types]

        response = self.client.get("/bytes/raw", params=params)
        self._verify_response(response)

        return response.json()  # type: ignore

    @retry_with_login
    def get_raws(self, query_filter: RawDataFilter) -> list[File]:
        params = query_filter.model_dump(exclude_none=True)
        params["mime_types"] = [m.value for m in query_filter.mime_types]

        response = self.client.get("/bytes/raws", params=params)
        self._verify_response(response)

        return response.json().get("files", [])
