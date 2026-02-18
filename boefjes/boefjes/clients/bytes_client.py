import typing
import uuid
from base64 import b64encode
from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog
from httpx import Client, HTTPStatusError, HTTPTransport, Response

from boefjes.config import settings
from boefjes.worker.interfaces import BoefjeOutput, BoefjeStorageInterface
from boefjes.worker.job_models import BoefjeMeta, NormalizerMeta, RawDataMeta

BYTES_API_CLIENT_VERSION = "0.3"
logger = structlog.get_logger(__name__)

ClientSessionMethod = Callable[..., Any]


def retry_with_login(function: ClientSessionMethod) -> ClientSessionMethod:
    @wraps(function)
    def wrapper(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except HTTPStatusError as error:
            if error.response.status_code != 401:
                raise

            self.login()
            return function(self, *args, **kwargs)

    return typing.cast(ClientSessionMethod, wrapper)


class BytesAPIClient(BoefjeStorageInterface):
    def __init__(self, base_url: str, username: str, password: str):
        self._session = Client(
            base_url=base_url,
            headers={"User-Agent": f"bytes-api-client/{BYTES_API_CLIENT_VERSION}"},
            transport=(HTTPTransport(retries=6)),
            timeout=settings.outgoing_request_timeout,
        )

        self.credentials = {"username": username, "password": password}
        self.headers: dict[str, str] = {}

    def login(self) -> None:
        self.headers = self._get_authentication_headers()

    @staticmethod
    def _verify_response(response: Response) -> None:
        try:
            response.raise_for_status()
        except HTTPStatusError as error:
            if error.response.status_code != 401 and error.response.status_code != 404:
                logger.error(response.text)
            else:
                logger.debug(response.text)
            raise

    def _get_authentication_headers(self) -> dict[str, str]:
        return {"Authorization": f"bearer {self._get_token()}"}

    def _get_token(self) -> str:
        response = self._session.post(
            "/token", data=self.credentials, headers={"content-type": "application/x-www-form-urlencoded"}
        )

        return str(response.json()["access_token"])

    @retry_with_login
    def save_boefje_meta(self, boefje_meta: BoefjeMeta) -> None:
        response = self._session.post("/bytes/boefje_meta", content=boefje_meta.model_dump_json(), headers=self.headers)

        self._verify_response(response)

    @retry_with_login
    def get_boefje_meta(self, boefje_meta_id: str) -> BoefjeMeta:
        response = self._session.get(f"/bytes/boefje_meta/{boefje_meta_id}", headers=self.headers)
        self._verify_response(response)

        return BoefjeMeta.model_validate_json(response.content)

    @retry_with_login
    def save_normalizer_meta(self, normalizer_meta: NormalizerMeta) -> None:
        response = self._session.post(
            "/bytes/normalizer_meta", content=normalizer_meta.model_dump_json(), headers=self.headers
        )

        self._verify_response(response)

    @retry_with_login
    def get_normalizer_meta(self, normalizer_meta_id: uuid.UUID) -> NormalizerMeta:
        response = self._session.get(f"/bytes/normalizer_meta/{normalizer_meta_id}", headers=self.headers)
        self._verify_response(response)

        return NormalizerMeta.model_validate_json(response.content)

    @retry_with_login
    def save_output(self, boefje_meta: BoefjeMeta, boefje_output: BoefjeOutput) -> dict[str, uuid.UUID]:
        self.save_boefje_meta(boefje_meta)

        if boefje_output.files:
            return self.save_raws(boefje_meta.id, boefje_output)

        return {}

    @retry_with_login
    def save_raws(self, boefje_meta_id: uuid.UUID, boefje_output: BoefjeOutput) -> dict[str, uuid.UUID]:
        response = self._session.post(
            "/bytes/raw",
            content=boefje_output.model_dump_json(),
            headers=self.headers,
            params={"boefje_meta_id": str(boefje_meta_id)},
        )
        self._verify_response(response)

        return response.json()

    @retry_with_login
    def save_raw(self, boefje_meta_id: str, raw: str | bytes, mime_types: set[str]) -> uuid.UUID:
        file_name = "raw"  # The name provides a key for all ids returned, so this is arbitrary as we only upload 1 file

        response = self._session.post(
            "/bytes/raw",
            json={
                "files": [
                    {
                        "name": file_name,
                        "content": b64encode(raw if isinstance(raw, bytes) else raw.encode()).decode(),
                        "tags": list(mime_types),
                    }
                ]
            },
            headers=self.headers,
            params={"boefje_meta_id": str(boefje_meta_id)},
        )
        self._verify_response(response)

        return uuid.UUID(response.json()[file_name])

    @retry_with_login
    def get_raw(self, raw_data_id: str) -> bytes:
        response = self._session.get(f"/bytes/raw/{raw_data_id}", headers=self.headers)
        self._verify_response(response)

        return response.content

    @retry_with_login
    def get_raws(self, boefje_meta_id: str) -> BoefjeOutput:
        response = self._session.get("/bytes/raws", headers=self.headers, params={"boefje_meta_id": boefje_meta_id})
        self._verify_response(response)

        return BoefjeOutput.model_validate_json(response.content)

    @retry_with_login
    def get_raw_meta(self, raw_data_id: str) -> RawDataMeta:
        response = self._session.get(f"/bytes/raw/{raw_data_id}/meta", headers=self.headers)
        self._verify_response(response)

        return RawDataMeta.model_validate_json(response.content)
